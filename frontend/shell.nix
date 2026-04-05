{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    # Python and backend dependencies
    python3
    python3Packages.pip
    python3Packages.virtualenv
    uv
    
    # Node.js for frontend
    nodejs_20
    nodePackages.npm
    
    # Development tools
    curl
    jq
    git
    
    # Docker for containers
    docker
    docker-compose
  ];
  
  shellHook = ''
    echo "🚀 AutoSRE × SuperPlane Development Environment Ready"
    echo "Backend: cd backend && uv sync && uv run python api_server.py"
    echo "Frontend: cd frontend && npm run dev"
    echo "SuperPlane: https://app.superplane.com"
  '';
}