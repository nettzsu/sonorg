{
  description = "sonorg: write a speech up, as an org file";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;

      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = lib.genAttrs systems;

      projectName =
        builtins.replaceStrings [ "_" "." ] [ "-" "-" ]
          (lib.toLower (lib.importTOML ./pyproject.toml).project.name);

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };

      editableOverlay = workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; };

      pythonSets = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          pyprojectOverrides = final: prev: { };
        in
        (pkgs.callPackage pyproject-nix.build.packages { python = pkgs.python312; }).overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.wheel
            overlay
            pyprojectOverrides
          ]
        )
      );

      runtimePath = system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        lib.makeBinPath (with pkgs; [
          yt-dlp
          ffmpeg
        ]);
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          pythonSet = pythonSets.${system}.overrideScope (
            lib.composeManyExtensions [
              editableOverlay
              (final: prev: {
                ${projectName} = prev.${projectName}.overrideAttrs (old: {
                  src = lib.fileset.toSource {
                    root = old.src;
                    fileset = lib.fileset.unions [
                      (old.src + "/pyproject.toml")
                      (old.src + "/README.md")
                      (lib.fileset.fileFilter (f: f.name == "__init__.py") (old.src + "/src"))
                    ];
                  };
                  nativeBuildInputs =
                    old.nativeBuildInputs ++ final.resolveBuildSystem { editables = [ ]; };
                });
              })
            ]
          );

          virtualenv = pythonSet.mkVirtualEnv "${projectName}-dev-env" workspace.deps.all;
        in
        {
          default = pkgs.mkShell {
            packages = [
              virtualenv
              pkgs.uv
              pkgs.yt-dlp
              pkgs.ffmpeg
            ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = pythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
              SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
            };
            shellHook = ''
              unset PYTHONPATH
              d=$PWD
              while [ ! -f "$d/pyproject.toml" ] && [ "$d" != / ]; do d=$(dirname "$d"); done
              export REPO_ROOT=$d
            '';
          };
        }
      );

      packages = forAllSystems (system: {
        default = pythonSets.${system}.mkVirtualEnv "${projectName}-env" workspace.deps.default;
      });

      apps = forAllSystems (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        wrapped = pkgs.writeShellScriptBin "sonorg" ''
          export PATH=${runtimePath system}:$PATH
          export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
          exec ${self.packages.${system}.default}/bin/sonorg "$@"
        '';
      in
      {
        default = {
          type = "app";
          program = "${wrapped}/bin/sonorg";
        };
      });
    };
}
