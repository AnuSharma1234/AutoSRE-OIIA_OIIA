{pkgs ? import <nixpkgs> {}}:
pkgs.mkShell {
  name = "autosre-dev";

  buildInputs = with pkgs; [
    kubectl
    kind
    docker
    jq
  ];
}
