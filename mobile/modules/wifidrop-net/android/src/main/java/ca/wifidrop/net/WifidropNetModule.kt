package ca.wifidrop.net

import android.content.Context
import android.net.Uri
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.util.Base64
import expo.modules.kotlin.exception.CodedException
import expo.modules.kotlin.functions.Coroutine
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import expo.modules.kotlin.records.Field
import expo.modules.kotlin.records.Record
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.CookieJar
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.io.InterruptedIOException
import java.security.MessageDigest
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

// Talks to the WiFiDrop PC over HTTPS. The PC makes its own certificate, so instead of the usual
// certificate authorities we trust exactly one key: the one whose SHA-256 "pin" came from the PC's
// QR code (or that the person confirmed by comparing the code shown on the PC).

class RequestOptions : Record {
  @Field val url: String = ""
  @Field val method: String = "GET"
  @Field val headers: Map<String, String> = emptyMap()
  @Field val body: String? = null
  @Field val bodyFile: String? = null // send part of a file instead (upload chunks)
  @Field val bodyOffset: Double = 0.0
  @Field val bodyLength: Double = -1.0 // -1: to the end of the file
  @Field val pin: String = ""
  @Field val timeoutMs: Double = 30000.0
}

class DownloadOptions : Record {
  @Field val id: String = ""
  @Field val url: String = ""
  @Field val headers: Map<String, String> = emptyMap()
  @Field val destination: String = ""
  @Field val pin: String = ""
}

private class PinMismatch : CertificateException("The server's key doesn't match the paired PC")

/** base64url(SHA-256(SubjectPublicKeyInfo)), matching the PC's tls.public_key_pin. */
internal fun pinOf(cert: X509Certificate): String =
  Base64.encodeToString(
    MessageDigest.getInstance("SHA-256").digest(cert.publicKey.encoded),
    Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP
  )

/** Trusts only the key with the expected pin; with no expected pin it accepts and records the key (probe). */
private class PinTrust(private val expected: String?) : X509TrustManager {
  @Volatile var seen: String? = null

  override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {
    throw CertificateException("Client certificates aren't used")
  }

  override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
    val leaf = chain.firstOrNull() ?: throw CertificateException("No certificate")
    val pin = pinOf(leaf)
    seen = pin
    if (expected != null && pin != expected) throw PinMismatch()
  }

  override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
}

class WifidropNetModule : Module() {
  private val clients = HashMap<String, OkHttpClient>()
  private var nsd: NsdManager? = null
  private var discovery: NsdManager.DiscoveryListener? = null
  private var multicastLock: WifiManager.MulticastLock? = null
  private val resolveQueue = ArrayDeque<NsdServiceInfo>()
  private var resolving = false

  override fun definition() = ModuleDefinition {
    Name("WifidropNet")

    Events("onProgress", "onServiceFound", "onServiceLost", "onDiscoveryError")

    AsyncFunction("request") Coroutine { options: RequestOptions ->
      withContext(Dispatchers.IO) { coded { request(options) } }
    }

    AsyncFunction("probe") Coroutine { url: String ->
      withContext(Dispatchers.IO) { coded { probe(url) } }
    }

    AsyncFunction("download") Coroutine { options: DownloadOptions ->
      withContext(Dispatchers.IO) { coded { download(options) } }
    }

    Function("startDiscovery") {
      startDiscovery()
    }

    Function("stopDiscovery") {
      stopDiscovery()
    }

    OnDestroy {
      stopDiscovery()
    }
  }

  // ---- HTTPS ----------------------------------------------------------------------------

  private fun build(trust: PinTrust): OkHttpClient {
    val tls = SSLContext.getInstance("TLS")
    tls.init(null, arrayOf<TrustManager>(trust), null)
    return OkHttpClient.Builder()
      .sslSocketFactory(tls.socketFactory, trust)
      // The pinned key is the PC's identity; its address changes from network to network.
      .hostnameVerifier { _, _ -> true }
      .cookieJar(CookieJar.NO_COOKIES)
      .followRedirects(false)
      .build()
  }

  private fun client(pin: String, timeoutMs: Long): OkHttpClient {
    val base = synchronized(clients) { clients.getOrPut(pin) { build(PinTrust(pin)) } }
    return base.newBuilder().callTimeout(timeoutMs, TimeUnit.MILLISECONDS).build()
  }

  private fun requestFor(url: String, method: String, headers: Map<String, String>, body: ByteArray?): Request {
    if (!url.startsWith("https://")) throw CodedException("BAD_URL", "That address isn't a WiFiDrop link.", null)
    val builder = Request.Builder().url(url)
    for ((k, v) in headers) builder.header(k, v)
    val needsBody = method in setOf("POST", "PUT", "PATCH", "DELETE")
    builder.method(method, body?.toRequestBody(null) ?: if (needsBody) ByteArray(0).toRequestBody(null) else null)
    return builder.build()
  }

  private fun openInput(uri: String): InputStream {
    if (uri.startsWith("content:")) {
      val resolver = appContext.reactContext?.contentResolver ?: throw IOException("No context")
      return resolver.openInputStream(Uri.parse(uri)) ?: throw IOException("Can't open $uri")
    }
    val path = if (uri.startsWith("file:")) Uri.parse(uri).path ?: uri else uri
    return File(path).inputStream()
  }

  private fun readSlice(uri: String, offset: Long, length: Long): ByteArray =
    openInput(uri).use { input ->
      var skipped = 0L
      while (skipped < offset) {
        val n = input.skip(offset - skipped)
        if (n <= 0) break
        skipped += n
      }
      if (length < 0) input.readBytes() else input.readNBytesCompat(length.toInt())
    }

  private fun InputStream.readNBytesCompat(count: Int): ByteArray {
    val out = ByteArray(count)
    var read = 0
    while (read < count) {
      val n = read(out, read, count - read)
      if (n < 0) break
      read += n
    }
    return if (read == count) out else out.copyOf(read)
  }

  private fun headerMap(response: Response): Map<String, String> =
    response.headers.names().associate { it.lowercase() to (response.header(it) ?: "") }

  private fun request(o: RequestOptions): Map<String, Any?> {
    val body = when {
      o.body != null -> o.body.toByteArray(Charsets.UTF_8)
      o.bodyFile != null -> readSlice(o.bodyFile, o.bodyOffset.toLong(), o.bodyLength.toLong())
      else -> null
    }
    client(o.pin, o.timeoutMs.toLong()).newCall(requestFor(o.url, o.method, o.headers, body)).execute().use { r ->
      return mapOf("status" to r.code, "headers" to headerMap(r), "body" to (r.body?.string() ?: ""))
    }
  }

  private fun probe(url: String): Map<String, Any?> {
    val trust = PinTrust(null)
    val client = build(trust).newBuilder().callTimeout(8, TimeUnit.SECONDS).build()
    client.newCall(requestFor(url, "GET", mapOf("X-WiFiDrop" to "1"), null)).execute().use { r ->
      val pin = trust.seen ?: throw CodedException("NO_KEY", "The PC didn't present a WiFiDrop security key.", null)
      return mapOf("pin" to pin, "status" to r.code, "body" to (r.body?.string() ?: ""))
    }
  }

  private fun download(o: DownloadOptions): Map<String, Any?> {
    client(o.pin, 0).newCall(requestFor(o.url, "GET", o.headers, null)).execute().use { r ->
      val body = r.body ?: throw IOException("Empty reply")
      if (r.code >= 400) return mapOf("status" to r.code, "body" to body.string())
      val path = if (o.destination.startsWith("file:")) Uri.parse(o.destination).path!! else o.destination
      val dest = File(path)
      dest.parentFile?.mkdirs()
      val part = File(dest.path + ".part")
      val total = body.contentLength()
      var written = 0L
      var reported = 0L
      body.byteStream().use { input ->
        part.outputStream().use { output ->
          val buffer = ByteArray(64 * 1024)
          while (true) {
            val n = input.read(buffer)
            if (n < 0) break
            output.write(buffer, 0, n)
            written += n
            if (written - reported >= 256 * 1024) {
              reported = written
              sendEvent("onProgress", mapOf("id" to o.id, "written" to written, "total" to total))
            }
          }
        }
      }
      dest.delete()
      if (!part.renameTo(dest)) throw IOException("Couldn't save the file")
      sendEvent("onProgress", mapOf("id" to o.id, "written" to written, "total" to total))
      return mapOf("status" to r.code, "uri" to Uri.fromFile(dest).toString(), "bytes" to written)
    }
  }

  private inline fun <T> coded(work: () -> T): T {
    try {
      return work()
    } catch (e: CodedException) {
      throw e
    } catch (e: IOException) {
      var cause: Throwable? = e
      while (cause != null) {
        if (cause is PinMismatch) {
          throw CodedException("PIN_MISMATCH", "This isn't the PC you paired with (its security key changed).", e)
        }
        cause = cause.cause
      }
      if (e is InterruptedIOException) throw CodedException("TIMEOUT", "The PC took too long to answer.", e)
      throw CodedException("NETWORK", e.message ?: "Couldn't reach the PC.", e)
    }
  }

  // ---- discovery ------------------------------------------------------------------------

  private fun startDiscovery() {
    stopDiscovery()
    val context = appContext.reactContext ?: return
    val manager = context.getSystemService(Context.NSD_SERVICE) as NsdManager
    val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    multicastLock = wifi.createMulticastLock("wifidrop-discovery").apply {
      setReferenceCounted(false)
      acquire()
    }
    val listener = object : NsdManager.DiscoveryListener {
      override fun onDiscoveryStarted(serviceType: String) {}
      override fun onDiscoveryStopped(serviceType: String) {}
      override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
        sendEvent("onDiscoveryError", mapOf("message" to "Discovery failed ($errorCode)"))
      }
      override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
      override fun onServiceFound(info: NsdServiceInfo) {
        synchronized(resolveQueue) { resolveQueue.addLast(info) }
        resolveNext()
      }
      override fun onServiceLost(info: NsdServiceInfo) {
        sendEvent("onServiceLost", mapOf("name" to info.serviceName))
      }
    }
    nsd = manager
    discovery = listener
    manager.discoverServices("_wifidrop._tcp", NsdManager.PROTOCOL_DNS_SD, listener)
  }

  // One resolve at a time: Android refuses overlapping ones.
  @Suppress("DEPRECATION")
  private fun resolveNext() {
    val manager = nsd ?: return
    val info = synchronized(resolveQueue) {
      if (resolving) return
      val next = resolveQueue.removeFirstOrNull() ?: return
      resolving = true
      next
    }
    manager.resolveService(info, object : NsdManager.ResolveListener {
      override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) = finished()
      override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
        val txt = serviceInfo.attributes.mapValues { (_, v) -> v?.toString(Charsets.UTF_8) ?: "" }
        sendEvent("onServiceFound", mapOf("name" to serviceInfo.serviceName, "txt" to txt))
        finished()
      }
    })
  }

  private fun finished() {
    synchronized(resolveQueue) { resolving = false }
    resolveNext()
  }

  private fun stopDiscovery() {
    val manager = nsd
    val listener = discovery
    if (manager != null && listener != null) {
      try {
        manager.stopServiceDiscovery(listener)
      } catch (_: IllegalArgumentException) {
        // already stopped
      }
    }
    nsd = null
    discovery = null
    synchronized(resolveQueue) {
      resolveQueue.clear()
      resolving = false
    }
    multicastLock?.let { if (it.isHeld) it.release() }
    multicastLock = null
  }
}
