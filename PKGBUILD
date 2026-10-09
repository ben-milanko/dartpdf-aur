# Maintainer: Ben Milanko <ben.milanko@protonmail.com>
pkgname=dartpdf-bin
pkgver=8.0.0
pkgrel=1
pkgdesc='Local PDF editor with annotations, forms, signatures and redaction'
arch=('x86_64')
url="https://dart-pdf.com"
license=('Apache-2.0')
# Candidate dependency list; validate direct ELF dependencies on Arch before
# publishing. Keep the complete upstream bundle, including its native plugins.
depends=('gtk3' 'libsecret')
# The bundled JNI helper links libjvm.so. Validate its runtime requirement
# separately rather than attributing it to OCR without evidence.
optdepends=('org.freedesktop.secrets: store digital-signing identities in a keyring')
provides=('dartpdf')
conflicts=('dartpdf')
options=('!strip')  # bundled .so files are already stripped; don't touch the AOT blob

source=("dartpdf-${pkgver}.tar.gz::https://github.com/ben-milanko/dart-pdf/releases/download/app-v${pkgver}/dartpdf-linux-x64.tar.gz"
        "LICENSE::https://raw.githubusercontent.com/ben-milanko/dart-pdf/app-v${pkgver}/LICENSE")

sha256sums=('3bb2bf6b940020de29ba45101680b70f758e83090b3b18eb09541c1c80b414f2'
            'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30')

package() {
  # The release tarball extracts the runner, data/, lib/, and share/ straight
  # into $srcdir. Install the runtime bundle under /opt/dartpdf; the
  # runner resolves its real path via readlink and finds data/ + lib/ next to
  # it, so a /usr/bin symlink works.
  install -d "${pkgdir}/opt/dartpdf"
  cp -r "${srcdir}/dart_pdf_editor_app" "${srcdir}/data" "${srcdir}/lib" \
        "${pkgdir}/opt/dartpdf/"
  chmod 755 "${pkgdir}/opt/dartpdf/dart_pdf_editor_app"

  install -d "${pkgdir}/usr/bin"
  ln -s /opt/dartpdf/dart_pdf_editor_app "${pkgdir}/usr/bin/dartpdf"
  # Release 8.0.0 includes the CLI. Fail rather than silently omit it.
  install -Dm755 "${srcdir}/dartpdf-cli" \
    "${pkgdir}/opt/dartpdf/dartpdf-cli"
  ln -s /opt/dartpdf/dartpdf-cli "${pkgdir}/usr/bin/dartpdf-cli"

  install -d "${pkgdir}/usr/share"
  cp -r "${srcdir}/share/." "${pkgdir}/usr/share/"

  install -Dm644 "${srcdir}/LICENSE" \
    "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
