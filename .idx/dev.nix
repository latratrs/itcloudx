{ pkgs, ... }: {
  channel = "stable-24.05";

  packages = [
    pkgs.nodejs_20
  ];

  idx = {
    previews = {
      enable = true;
      previews = {
        astrowind = {
          command = [
            "bash" "-c"
            "cd astrowind && npm install && npx astro dev --host 0.0.0.0 --port 4321"
          ];
          manager = "web";
        };
        cms = {
          command = [
            "bash" "-c"
            "cd cms && npm install && NODE_OPTIONS=--no-deprecation next dev -p 3000 -H 0.0.0.0"
          ];
          manager = "web";
        };
      };
    };
  };
}