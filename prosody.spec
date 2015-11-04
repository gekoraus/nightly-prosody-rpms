%global sslcert    %{_sysconfdir}/pki/%{name}/localhost.crt
%global sslkey     %{_sysconfdir}/pki/%{name}/localhost.key
%global luaver     5.1

Summary:           Flexible communications server for Jabber/XMPP
Name:              prosody
Version:           0.10
Release:           1.nightly172%{?dist}
License:           MIT
Group:             System Environment/Daemons
URL:               https://prosody.im/
Source0:           http://prosody.im/nightly/0.10/build172/%{name}-%{version}-1nightly172.tar.gz
Source1:           prosody.init
Source2:           prosody.logrotate-init
Source3:           prosody.service
Source4:           prosody.logrotate-service
Source5:           prosody.tmpfilesd
Source6:           prosody-localhost.cfg.lua
Source7:           prosody-example.com.cfg.lua
Patch0:            prosody-0.10-config.patch
Patch1:            prosody-0.10-rhel5.patch
BuildRequires:     libidn-devel, openssl-devel
Requires(pre):     shadow-utils
%if 0%{?rhel} > 6 || 0%{?fedora} > 17
Requires(post):    systemd, %{_bindir}/openssl
Requires(preun):   systemd
Requires(postun):  systemd
BuildRequires:     systemd
%else
Requires(post):    /sbin/chkconfig, %{_bindir}/openssl
Requires(preun):   /sbin/service, /sbin/chkconfig
Requires(postun):  /sbin/service
%endif
%if 0%{?rhel} > 7 || 0%{?fedora} > 19
# Prosody does not work with lua >= 5.2, so use compat-lua instead of lua
# on Fedora >= 20; luajit (compatible with 5.1) would be second choice.
Requires:          compat-lua, lua-filesystem-compat, lua-expat-compat
Requires:          lua-socket-compat, lua-sec-compat
BuildRequires:     compat-lua-devel
%else
%if 0%{?rhel} > 6 || 0%{?fedora} > 15
Requires:          lua(abi) = %{luaver}
%else
Requires:          lua >= %{luaver}
%endif
Requires:          lua-filesystem, lua-expat, lua-socket, lua-sec
BuildRequires:     lua-devel
%endif
BuildRoot:         %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

%description
Prosody is a flexible communications server for Jabber/XMPP written in Lua.
It aims to be easy to use, and light on resources. For developers it aims
to be easy to extend and give a flexible system on which to rapidly develop
added functionality, or prototype new protocols.

%prep
%setup -q -n %{name}-%{version}-1nightly172
%patch0 -p1 -b .config
%if 0%{?rhel} == 5
%patch1 -p1
%endif
rm -f core/certmanager.lua.config

%build
# CFLAG -D_GNU_SOURCE requires fallocate() which requires GLIBC >= 2.10
./configure \
  --prefix=%{_prefix} \
  --libdir=%{_libdir} \
%if 0%{?rhel} > 7 || 0%{?fedora} > 19
  --with-lua-include=%{_includedir}/lua-%{luaver} \
  --runwith=lua-%{luaver} \
%endif
%if 0%{?rhel} != 5
  --cflags="$RPM_OPT_FLAGS -fPIC -D_GNU_SOURCE" \
%else
  --cflags="$RPM_OPT_FLAGS -fPIC" \
%endif
  --ldflags="$RPM_LD_FLAGS -shared" \
  --no-example-certs
make %{?_smp_mflags}

# Make prosody-migrator
make -C tools/migration %{?_smp_mflags}

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT{%{_sysconfdir}/pki,%{_localstatedir}/{lib,log}/%{name}}/
make DESTDIR=$RPM_BUILD_ROOT install

# Install prosody-migrator
make -C tools/migration DESTDIR=$RPM_BUILD_ROOT install

# Install ejabberd2prosody
install -p -m 755 tools/ejabberd2prosody.lua $RPM_BUILD_ROOT%{_bindir}/ejabberd2prosody
sed -e 's@;../?.lua@;%{_libdir}/%{name}/util/?.lua;%{_libdir}/%{name}/?.lua;@' \
%if 0%{?rhel} > 7 || 0%{?fedora} > 19
  -e '1s@ lua$@ lua-%{luaver}@' \
%endif
  -i $RPM_BUILD_ROOT%{_bindir}/ejabberd2prosody
touch -c -r tools/ejabberd2prosody.lua $RPM_BUILD_ROOT%{_bindir}/ejabberd2prosody
install -p -m 644 tools/erlparse.lua $RPM_BUILD_ROOT%{_libdir}/%{name}/util/

# Move certificates directory and symlink it
mv -f $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/certs/ $RPM_BUILD_ROOT%{_sysconfdir}/pki/%{name}/
ln -s ../pki/%{name}/ $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/certs

# Install systemd/tmpfiles or initscript files
%if 0%{?fedora} >= 15 || 0%{?rhel} >= 7
install -D -p -m 644 %{SOURCE3} $RPM_BUILD_ROOT%{_unitdir}/%{name}.service
install -D -p -m 644 %{SOURCE4} $RPM_BUILD_ROOT%{_sysconfdir}/logrotate.d/%{name}
install -D -p -m 644 %{SOURCE5} $RPM_BUILD_ROOT%{_tmpfilesdir}/%{name}.conf
mkdir -p $RPM_BUILD_ROOT/run/%{name}
%else
install -D -p -m 755 %{SOURCE1} $RPM_BUILD_ROOT%{_sysconfdir}/rc.d/init.d/%{name}
install -D -p -m 644 %{SOURCE2} $RPM_BUILD_ROOT%{_sysconfdir}/logrotate.d/%{name}
mkdir -p $RPM_BUILD_ROOT%{_localstatedir}/run/%{name}
sed -e 's@/run@%{_localstatedir}/run@' -i $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/prosody.cfg.lua
%endif

# Keep configuration file timestamp
touch -c -r prosody.cfg.lua.dist.config $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/prosody.cfg.lua

# Install virtual host configuration
install -D -p -m 644 %{SOURCE6} $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/conf.d/localhost.cfg.lua
install -D -p -m 644 %{SOURCE7} $RPM_BUILD_ROOT%{_sysconfdir}/%{name}/conf.d/example.com.cfg.lua

# Fix permissions for rpmlint
chmod 755 $RPM_BUILD_ROOT%{_libdir}/%{name}/util/*.so

# Fix incorrect end-of-line encoding
sed -e 's/\r//g' -i doc/stanza.txt doc/session.txt doc/roster_format.txt

%clean
rm -rf $RPM_BUILD_ROOT

%pre
getent group %{name} > /dev/null || %{_sbindir}/groupadd -r %{name}
getent passwd %{name} > /dev/null || %{_sbindir}/useradd -r -g %{name} -d %{_localstatedir}/lib/%{name} -s /sbin/nologin -c "Prosody XMPP Server" %{name}
exit 0

%post
%if 0%{?rhel} > 6 || 0%{?fedora} > 17
%systemd_post %{name}.service
%else
/sbin/chkconfig --add %{name}
%endif

if [ ! -f %{sslkey} ]; then
  umask 077
  %{_bindir}/openssl genrsa 2048 > %{sslkey} 2> /dev/null
  chown root:%{name} %{sslkey}
  chmod 640 %{sslkey}
fi

if [ ! -f %{sslcert} ]; then
  FQDN=`hostname`
  if [ "x${FQDN}" = "x" ]; then
    FQDN=localhost.localdomain
  fi

  cat << EOF | %{_bindir}/openssl req -new -key %{sslkey} -x509 -sha256 -days 365 -set_serial $RANDOM -out %{sslcert} 2> /dev/null
--
SomeState
SomeCity
SomeOrganization
SomeOrganizationalUnit
${FQDN}
root@${FQDN}
EOF
  chmod 644 %{sslcert}
fi

%preun
%if 0%{?rhel} > 6 || 0%{?fedora} > 17
%systemd_preun %{name}.service
%else
if [ $1 -eq 0 ]; then
  /sbin/service %{name} stop > /dev/null 2>&1 || :
  /sbin/chkconfig --del %{name}
fi
%endif

%postun
%if 0%{?rhel} > 6 || 0%{?fedora} > 17
%systemd_postun_with_restart %{name}.service
%else
if [ $1 -ne 0 ]; then
  /sbin/service %{name} condrestart > /dev/null 2>&1 || :
fi
%endif

%files
%defattr(-,root,root,-)
%{!?_licensedir:%global license %%doc}
%license COPYING
%doc AUTHORS HACKERS README doc/*
%{_bindir}/%{name}
%{_bindir}/%{name}ctl
%{_bindir}/%{name}-migrator
%{_bindir}/ejabberd2prosody
%{_libdir}/%{name}/
%dir %attr(750,root,%{name}) %{_sysconfdir}/pki/%{name}/
%config(noreplace) %attr(0640,root,%{name}) %{_sysconfdir}/pki/%{name}/*
%dir %attr(750,root,%{name}) %{_sysconfdir}/%{name}/
%config(noreplace) %attr(0640,root,%{name}) %{_sysconfdir}/%{name}/*.cfg.lua
%dir %attr(750,root,%{name}) %{_sysconfdir}/%{name}/conf.d/
%config(noreplace) %attr(0640,root,%{name}) %{_sysconfdir}/%{name}/conf.d/*.cfg.lua
%attr(750,root,%{name}) %{_sysconfdir}/%{name}/certs
%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%if 0%{?rhel} > 6 || 0%{?fedora} > 17
%{_unitdir}/%{name}.service
%{_tmpfilesdir}/%{name}.conf
%dir %attr(0755,%{name},%{name}) /run/%{name}/
%else
%{_sysconfdir}/rc.d/init.d/%{name}
%dir %attr(0755,%{name},%{name}) %{_localstatedir}/run/%{name}/
%endif
%dir %attr(750,%{name},%{name}) %{_localstatedir}/lib/%{name}/
%dir %attr(750,%{name},%{name}) %{_localstatedir}/log/%{name}/
%{_mandir}/man1/%{name}*.1*

%changelog
* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly172
- Upgrade to 0.10-1.nightly172

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly171
- Upgrade to 0.10-1.nightly171

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly170
- Upgrade to 0.10-1.nightly170

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly169
- Upgrade to 0.10-1.nightly169

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly168
- Upgrade to 0.10-1.nightly168

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly167
- Upgrade to 0.10-1.nightly167

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly166
- Upgrade to 0.10-1.nightly166

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly165
- Upgrade to 0.10-1.nightly165

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly164
- Upgrade to 0.10-1.nightly164

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly163
- Upgrade to 0.10-1.nightly163

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly162
- Upgrade to 0.10-1.nightly162

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly161
- Upgrade to 0.10-1.nightly161

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly160
- Upgrade to 0.10-1.nightly160

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly159
- Upgrade to 0.10-1.nightly159

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly158
- Upgrade to 0.10-1.nightly158

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly157
- Upgrade to 0.10-1.nightly157

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly156
- Upgrade to 0.10-1.nightly156

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly155
- Upgrade to 0.10-1.nightly155

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly154
- Upgrade to 0.10-1.nightly154

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly153
- Upgrade to 0.10-1.nightly153

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly152
- Upgrade to 0.10-1.nightly152

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly151
- Upgrade to 0.10-1.nightly151

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly150
- Upgrade to 0.10-1.nightly150

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly149
- Upgrade to 0.10-1.nightly149

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly148
- Upgrade to 0.10-1.nightly148

* Wed Nov 04 2015 Robert Scheck <robert@fedoraproject.org> 0.10-1.nightly147
- Upgrade to 0.10-1.nightly147

* Sun Sep 27 2015 Robert Scheck <robert@fedoraproject.org> 0.9.8-6
- Fixed shebang for ejabberd2prosody
- Backported support for IPv6 DNS servers (#1256677)

* Sun Jul 23 2015 Robert Scheck <robert@fedoraproject.org> 0.9.8-5
- Start after network-online.target not network.target (#1256062)

* Wed Jul 15 2015 Robert Scheck <robert@fedoraproject.org> 0.9.8-4
- Change default CA paths to /etc/pki/tls/certs(/ca-bundle.crt)

* Wed Jul 01 2015 Robert Scheck <robert@fedoraproject.org> 0.9.8-3
- Fixed the wrong logrotate configuration to not use a wildcard

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.8-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sat Apr 18 2015 Robert Scheck <robert@fedoraproject.org> 0.9.8-1
- Upgrade to 0.9.8 (#1152126)

* Sat Feb 14 2015 Robert Scheck <robert@fedoraproject.org> 0.9.7-1
- Upgrade to 0.9.7 (#985563, #1152126)

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.4-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.4-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Tue Jun 03 2014 Jan Kaluza <jkaluza@redhat.com> - 0.9.4-2
- add missing lua-socket-compat dependency

* Fri May 30 2014 Jan Kaluza <jkaluza@redhat.com> - 0.9.4-1
- update to version 0.9.4
- build with luajit

* Wed Sep 11 2013 Johan Cwiklinski <johan AT x-tnd DOT be> - 0.9.1-1
- Update to 0.9.1

* Thu Aug 22 2013 Matěj Cepl <mcepl@redhat.com> - 0.9.0-1
- Final upstream release.

* Wed Aug 07 2013 Johan Cwiklinski <johan AT x-tnd DOT be> - 0.9.0-0.5.rc5
- Update to 0.9.0rc5

* Fri Jun 21 2013 Johan Cwiklinski <johan AT x-tnd DOT be> - 0.9.0-0.4.rc4
- Update to 0.9.0rc4

* Fri Jun 21 2013 Johan Cwiklinski <johan AT x-tnd DOT be> - 0.9.0-0.3.rc3
- Update to 0.9.0rc3

* Fri Jun 07 2013 Johan Cwiklinski <johan AT x-tnd DOT be> - 0.9.0-0.2.rc2
- Update to 0.9.0rc2

* Wed May 15 2013 Tom Callaway <spot@fedoraproject.org> - 0.9.0-0.1.beta1
- update to 0.9.0beta1, rebuild for lua 5.2

* Sat Apr 27 2013 Robert Scheck <robert@fedoraproject.org> - 0.8.2-9
- Apply wise permissions to %%{_sysconfdir}/%%{name} (#955384)
- Apply wise permissions to default SSL certificates (#955380)
- Do not ship %%{_sysconfdir}/%%{name}/certs by default (#955385)

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.2-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Sep 27 2012 Johan Cwiklinski <johan At x-tnd DOt be> 0.8.2-7
- Use systemd-rpm macros, bz #850282

* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.2-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Mon May 07 2012 Johan Cwiklinski <johan AT x-tnd DOT be> 0.8.2-5
- Missing rhel %%ifs
- Change the way SSL certificate is generated

* Sun May 06 2012 Johan Cwiklinski <johan AT x-tnd DOT be> 0.8.2-4
- ghost %%{_localstatedir}/run/%%{name}

* Sun May 06 2012 Johan Cwiklinski <johan AT x-tnd DOT be> 0.8.2-3
- Add missing requires
- Add rhel %%ifs

* Mon Mar 05 2012 Johan Cwiklinski <johan AT x-tnd DOT be> 0.8.2-2
- Switch to systemd for Fedora >= 15, keep sysv for EPEL builds
- Remove some macros that should not be used

* Thu Jun 23 2011 Johan Cwiklinski <johan AT x-tnd DOT be> 0.8.2-1.trashy
- 0.8.2

* Tue Jun 7 2011 Johan Cwiklinski <johan AT x-tnd DOT be> 0.8.1-1.trashy
- 0.8.1

* Sun May 8 2011 Johan Cwiklinski <johan AT x-tnd DOT be> 0.8.0-3.trashy
- tmpfiles.d configuration for F-15

* Sat Apr 16 2011 Johan Cwiklinski <johan AT x-tnd DOT be> 0.8.0-2.trashy
- Now requires lua-dbi

* Fri Apr 8 2011 Johan Cwiklinski <johan AT x-tnd DOT be> 0.8.0-1.trashy
- 0.8.0

* Sun Jan 23 2011 Johan Cwiklinski <johan AT x-tnd DOT be> 0.7.0-4.trashy
- Redefine _initddir and _sharedstatedir marcos for EL-5

* Sat Dec 11 2010 Johan Cwiklinski <johan AT x-tnd DOT be> 0.7.0-3
- Apply ssl patch before sed on libdir; to avoid a patch context issue 
  building on i686 

* Sat Sep 11 2010 Johan Cwiklinski <johan AT x-tnd DOT be> 0.7.0-2
- No longer ships default ssl certificates, generates one at install

* Wed Jul 14 2010 Johan Cwiklinski <johan AT x-tnd DOT be> 0.7.0-1
- Update to 0.7.0

* Wed Apr 28 2010 Johan Cwiklinski <johan AT x-tnd DOT be> 0.6.2-1
- Update to 0.6.2

* Thu Dec 31 2009 Johan Cwiklinski <johan AT x-tnd DOT be> 0.6.1-1
- Initial packaging
