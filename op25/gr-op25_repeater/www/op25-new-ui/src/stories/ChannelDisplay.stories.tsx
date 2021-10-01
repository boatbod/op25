import { ComponentStory, ComponentMeta } from "@storybook/react";
import { Grid } from "@material-ui/core";
import ChannelDisplay from "components/ChannelDisplay";
import { dummyData } from "redux/app/store";

// @ts-ignore
import docs from "./ChannelDisplayDocs.mdx";

export default {
  title: "OP25/Channel Display",
  component: ChannelDisplay,
  parameters: {
    docs: {
      page: docs,
    },
  },
  args: {
    channelId: 1,
  },
  argTypes: {
    channelId: {
      options: dummyData.op25.channels.map((channel) => channel.id),
      control: { type: "select" },
    },
    className: { table: { disable: true } },
    onChannelHoldTalkgroup: {
      action: "Hold button clicked",
      table: { disable: true },
    },
    onGoToTalkgroup: {
      action: "GoTo button clicked",
      table: { disable: true },
    },
    onReloadChannel: {
      action: "Reload button clicked",
      table: { disable: true },
    },
    onBlacklistTalkgroup: {
      action: "B/LIST button clicked",
      table: { disable: true },
    },
    onWhitelistTalkgroup: {
      action: "W/LIST button clicked",
      table: { disable: true },
    },
    onLogVerboseChange: {
      action: "LOG/V button clicked",
      table: { disable: true },
    },
    onSkipTalkgroup: {
      action: "Skip button clicked",
      table: { disable: true },
    },
  },
} as ComponentMeta<typeof ChannelDisplay>;

const Template: ComponentStory<typeof ChannelDisplay> = (args) => (
  <Grid container spacing={2} justifyContent="center">
    <Grid item xs={12} md={6}>
      <ChannelDisplay {...args} />
    </Grid>
  </Grid>
);

export const DarkTheme = Template.bind({});
DarkTheme.args = {};
DarkTheme.storyName = "Dark Theme";
DarkTheme.parameters = {
  theme: "dark",
};

export const LightTheme = Template.bind({});
LightTheme.args = {};
LightTheme.storyName = "Light Theme";
LightTheme.parameters = {
  theme: "light",
};
