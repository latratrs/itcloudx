{ pkgs, ... }: {
  channel = "stable-23.11";

  packages = [
    pkgs.nodejs_20
    pkgs.git
  ];

  idx = {
    extensions = [
      "astro-build.astro-vscode"
      "mongodb.mongodb-vscode"
    ];

    # FIXED: Lifecycle hooks must be inside 'workspace'
    workspace = {
      onCreate = {
        # This runs only the first time the workspace is created
        install-deps = "cd cms && npm install && cd ../astrowind && npm install";
      };
      onStart = {
        # Optional: Run commands every time the workspace starts
      };
    };

    previews = {
      enable = true;
      previews = {
        payload = {
          command = ["npm" "run" "dev" "--prefix" "cms"];
          manager = "web";
          env = { PORT = "3000"; };
        };
        astro = {
          command = ["npm" "run" "dev" "--prefix" "astrowind"];
          manager = "web";
          env = { PORT = "4321"; };
        };
      };
    };
  };
}