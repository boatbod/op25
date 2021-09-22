const path = require("path");
const TsconfigPathsPlugin = require("tsconfig-paths-webpack-plugin");

// Solution found at https://github.com/storybookjs/storybook/issues/3291#issuecomment-686760728

module.exports = {
  stories: ["../src/**/*.stories.mdx", "../src/**/*.stories.@(js|jsx|ts|tsx)"],
  addons: [
    "@storybook/addon-links",
    "@storybook/addon-essentials",
    "@storybook/preset-create-react-app",
  ],
  webpackFinal: async (config) => {
    config.resolve.plugins = [
      new TsconfigPathsPlugin({
        configFile: path.resolve(__dirname, "../tsconfig.json"),
      }),
    ];

    // Return the altered config
    return config;
  },
};
