{ pkgs, ... }: {

  packages = [
    pkgs.nodejs_20
    pkgs.yarn
    pkgs.git
    pkgs.python3
    pkgs.gcc
    pkgs.gnumake
    pkgs.openssl
    pkgs.curl
    pkgs.jq
  ];

  env = {
    NODE_ENV = "development";
  };

  idx = {
    extensions = [];

    previews = {
      enable = true;
      previews = {
        web = {
          command = [
            "bash" "-c"
            "cd /home/user/itcloudx/astrowind && npx astro dev --host 0.0.0.0 --port $PORT"
          ];
          manager = "web";
        };
      };
    };

    workspace = {
      onCreate = {
        install = "cd /home/user/itcloudx/astrowind && npm install";
      };
      onStart = {
        dev-server = "cd /home/user/itcloudx/astrowind && npx astro dev --host 0.0.0.0 --port 4321";
      };
    };
  };
}