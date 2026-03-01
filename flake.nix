{
  description = "quawk: POSIX-oriented AWK compiler/JIT project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    qcheck = {
      url = "github:league/qcheck";
      flake = false;
    };
    oneTrueAwk = {
      url = "github:onetrueawk/awk";
      flake = false;
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      qcheck,
      oneTrueAwk,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs { inherit system; }));
    in
    {
      packages = forAllSystems (pkgs: {
        default = pkgs.stdenvNoCC.mkDerivation {
          pname = "quawk-docs";
          version = "0.1.0";
          src = pkgs.lib.cleanSource ./.;
          dontBuild = true;

          installPhase = ''
            runHook preInstall
            mkdir -p "$out/share/doc/quawk"
            cp README.md GRAMMAR.md BUILD.md PLAN.md TASKS.md STRATEGY.md EXECUTION.md TESTING.md TEST_SPEC.md CI.md LICENSE "$out/share/doc/quawk/"
            runHook postInstall
          '';

          meta = with pkgs.lib; {
            description = "Documentation package for quawk";
            license = licenses.bsd3;
            platforms = platforms.unix;
          };
        };
      });

      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          QCHECK_SRC = "${qcheck}";
          ONE_TRUE_AWK_SRC = "${oneTrueAwk}";

          packages = with pkgs; [
            mlton
            llvm
            clang
            lld
            gnumake
            pkg-config
            gawk
            jq
            nixpkgs-fmt
          ];
        };
      });

      formatter = forAllSystems (pkgs: pkgs.nixpkgs-fmt);

      checks = forAllSystems (pkgs: {
        docs = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      });
    };
}
