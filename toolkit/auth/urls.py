from django.conf.urls.defaults import patterns, url

urlpatterns = patterns( 'toolkit.auth.views',
    url('^(?P<atype>read|write)', 'auth', name="auth"),
    url('^logout', 'clear_auth', name="logout"),
)
