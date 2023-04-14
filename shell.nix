{}:

let pkgs = import (builtins.fetchTarball {
  url = "https://github.com/NixOS/nixpkgs/archive/fe2ecaf706a5907b5e54d979fbde4924d84b65fc.tar.gz";
  sha256 = "0nawb6fcsyijxhbib8zhf1xsxz8zl99iw0pjv15z829fqqg50ir4";
}) {}; in

pkgs.mkShell {
    nativeBuildInputs = (with pkgs; [
        python39
        go
    ]);
}
