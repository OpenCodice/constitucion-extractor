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
- `letsencrypt-yr2.pem` — Let's Encrypt YR2 (emisor: ISRG Root YR; vence en
  2028). SHA-256
  `23:8B:85:A0:09:9C:65:B9:70:47:7D:57:24:F1:A1:D4:75:CE:50:58:CF:FE:4E:FA:87:33:89:9B:DB:86:3C:47`.
  Fuente: http://yr2.i.lencr.org/
- `isrg-root-yr-cross-x1.pem` — ISRG Root YR firmada por ISRG Root X1 (vence en
  2032), para llegar a una raíz que los runners ya tienen. SHA-256
  `07:26:39:D0:B1:40:D5:BF:FA:E1:6A:D9:C3:F6:CC:60:86:04:06:21:F5:1E:E6:1A:6D:46:A8:91:5C:07:CF:76`.
  Fuente: http://yr.i.lencr.org/

  Los dos los necesita CDMX (data.consejeria.cdmx.gob.mx envía intermedios de
  DigiCert que no son los de su certificado).

`scripts/resolver_pdf.py` también los usa al leer las páginas índice.
