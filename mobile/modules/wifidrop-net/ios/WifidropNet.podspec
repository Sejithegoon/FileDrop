Pod::Spec.new do |s|
  s.name           = 'WifidropNet'
  s.version        = '1.0.0'
  s.summary        = 'Pinned HTTPS and network discovery for WiFiDrop'
  s.description    = 'Talks to the WiFiDrop PC over HTTPS, trusting only its pinned key, and finds it on the Wi-Fi.'
  s.author         = ''
  s.homepage       = 'https://wifidrop.ca'
  s.platforms      = {
    :ios => '16.4'
  }
  s.source         = { git: '' }
  s.static_framework = true

  s.dependency 'ExpoModulesCore'

  # Swift/Objective-C compatibility
  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
  }

  s.source_files = "**/*.{h,m,mm,swift,hpp,cpp}"
end
