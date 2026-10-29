"""Package the dependency-free watch frontend and install it through VS Code."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape, quoteattr
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.test_storage import scratch_descriptors, scratch_directory


def package(destination):
    source = ROOT / 'vscode/onpc-watch'
    manifest = json.loads((source / 'package.json').read_text())
    metadata = f'''<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id={quoteattr(manifest['name'])} Version={quoteattr(manifest['version'])} Publisher={quoteattr(manifest['publisher'])}/>
    <DisplayName>{escape(manifest['displayName'])}</DisplayName>
    <Description xml:space="preserve">{escape(manifest['description'])}</Description>
    <Tags>watch,testing</Tags><Categories>Testing,Visualization</Categories><GalleryFlags/>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value={quoteattr(manifest['engines']['vscode'])}/>
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace"/>
    </Properties>
    <License>extension/LICENSE</License>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>
    <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true"/>
    <Asset Type="Microsoft.VisualStudio.Services.Content.License" Path="extension/LICENSE" Addressable="true"/>
  </Assets>
</PackageManifest>'''
    types = '''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json"/>
  <Default Extension=".vsixmanifest" ContentType="text/xml"/>
  <Default Extension=".js" ContentType="application/javascript"/>
  <Default Extension=".css" ContentType="text/css"/>
  <Default Extension=".png" ContentType="image/png"/>
  <Default Extension=".md" ContentType="text/markdown"/>
</Types>'''
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('extension.vsixmanifest', metadata)
        archive.writestr('[Content_Types].xml', types)
        # A finite payload avoids bundling workspace files or generated artifacts.
        for name in ('package.json', 'extension.js', 'media/watch.js', 'media/watch.css',
                     'media/app-logo.png', 'README.md'):
            archive.write(source / name, 'extension/' + name)
        archive.write(ROOT / 'LICENSE', 'extension/LICENSE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--if-available', action='store_true')
    args = parser.parse_args()
    cli = next((found for name in ('code', 'code-insiders', 'codium')
                if (found := shutil.which(name))), None)
    if cli is None or os.geteuid() == 0:
        message = ('VS Code CLI not found (code, code-insiders or codium)' if cli is None else
                   'run as the desktop user to install a user extension')
        if args.if_available:
            print(f'setup: watch extension skipped: {message}; use ./setup.sh --watch later')
            return 0
        print(f'setup: watch extension: {message}', file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix='onpc-watch-extension-', dir=scratch_directory()) as directory:
        vsix = Path(directory) / 'onpc-watch.vsix'
        package(vsix)
        result = subprocess.run([cli, '--install-extension', str(vsix), '--force'],
                                cwd=ROOT, pass_fds=scratch_descriptors(), check=False, timeout=120)
        if result.returncode:
            return result.returncode
    print('setup: ONPC Watch installed; reload VS Code, then Ctrl+Shift+P → ONPC: Watch')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
