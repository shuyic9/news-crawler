{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    systems.url = "github:nix-systems/default-linux";
  };

  outputs = {
    nixpkgs,
    systems,
    ...
  }: let
    inherit (nixpkgs) lib;
    forSystems = f:
      lib.genAttrs (import systems) (system: f nixpkgs.legacyPackages.${system});
  in {
    devShells = forSystems (pkgs: {
      default = pkgs.mkShell {
        nativeBuildInputs = [
          (pkgs.python3.withPackages (p: [
            p.requests
            p.scrapy
            p.scrapy-splash

            (p.buildPythonPackage rec {
              pname = "scrapy_playwright";
              version = "0.0.38";
              format = "setuptools";

              src = p.fetchPypi {
                inherit pname version;
                hash = "sha256-ffBED9RkIxIrKtt8xn7ESdYstdfuMEu6eiCo4yb6BdA=";
              };

              propagatedBuildInputs = with p; [
                scrapy
                playwright
              ];

              pythonImportsCheck = [ "scrapy_playwright" ];
            })
          ]))

          pkgs.python3Packages.python-lsp-server
          pkgs.python3Packages.python-lsp-ruff
          pkgs.python3Packages.pylsp-mypy
        ];

        PLAYWRIGHT_BROWSERS_PATH = pkgs.playwright-driver.browsers-chromium;
      };
    });

    formatter = forSystems (pkgs: pkgs.alejandra);
  };
}
