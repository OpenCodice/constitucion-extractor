# Certificados intermedios

Algunos servidores de congresos estatales no envían el certificado intermedio de
su cadena TLS. Los navegadores y macOS lo completan solos; curl en Linux (donde
corre la vigilancia) no, y la descarga falla. La vigilancia añade estos
intermedios públicos al almacén del sistema: la cadena se sigue validando hasta
una raíz de confianza del runner.

- `sectigo-public-server-authentication-ca-dv-r36.pem` — Sectigo Public Server
  Authentication CA DV R36 (emisor: Root R46; vence en 2036). SHA-256
  `8C:54:C3:34:B6:6B:A4:E4:26:77:2A:F4:A3:F9:13:6C:19:A1:AE:C7:29:FD:B2:8C:53:5C:07:A5:A4:EF:22:E0`.
  Lo necesitan Hidalgo y Tlaxcala. Fuente: http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt
