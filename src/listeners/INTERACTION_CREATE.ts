// The case of the file name is just to signify that
// this is listening to an event directly from the gateway

import { SlashCommandMessage } from "@fire/lib/extensions/slashCommandMessage";
import { SlashCommand } from "@fire/lib/interfaces/slashCommands";
import { constants } from "@fire/lib/util/constants";
import { Listener } from "@fire/lib/util/listener";
import { DMChannel } from "discord.js";
import { Scope } from "@sentry/node";

const { emojis } = constants;

export default class InteractionCreate extends Listener {
  constructor() {
    super("INTERACTION_CREATE", {
      emitter: "gateway",
      event: "INTERACTION_CREATE",
    });
  }

  async exec(command: SlashCommand) {
    if (!command) return;
    try {
      // should be cached if in guild or fetch if dm channel
      await this.client.channels.fetch(command.channel_id).catch(() => {});
      const message = new SlashCommandMessage(this.client, command);
      await message.channel.ack((message.flags & 64) != 0);
      if (!message.command) {
        this.client.console.warn(
          `[Commands] Got slash command request for unknown command, /${command.data.name}`
        );
        return await message.error("UNKNOWN_COMMAND");
      } else if (!message.guild && message.command.channel == "guild")
        return await message.error(
          "SLASH_COMMAND_BOT_REQUIRED",
          this.client.config.inviteLink
        );
      await message.generateContent();
      // @ts-ignore
      await this.client.commandHandler.handle(message);
      // if (message.sent != "message")
      //   await message.sourceMessage?.delete().catch(() => {});
    } catch (error) {
      const guild = this.client.guilds.cache.get(command.guild_id);
      if (!guild)
        await this.callbackError(command, error).catch(
          async () => await this.webhookError(command, error).catch(() => {})
        );
      if (typeof this.client.sentry != "undefined") {
        const sentry = this.client.sentry;
        sentry.setExtras({
          slashCommand: JSON.stringify(command.data),
          member: command.member
            ? `${command.member.user.username}#${command.member.user.discriminator}`
            : `${command.user.username}#${command.user.discriminator}`,
          channel_id: command.channel_id,
          guild_id: command.guild_id,
          env: process.env.NODE_ENV,
        });
        sentry.captureException(error);
        sentry.configureScope((scope: Scope) => {
          scope.setUser(null);
          scope.setExtras(null);
        });
      }
    }
  }

  async callbackError(command: SlashCommand, error: Error) {
    await this.client.req
      .interactions(command.id)(command.token)
      .callback.post({
        data: {
          type: 3,
          data: {
            content: `${emojis.error} An error occured while trying to handle this command that may be caused by being in DMs or the bot not being present...

Try inviting the bot (<${this.client.config.inviteLink}>) and try again.

Error Message: ${error.message}`,
            flags: 64,
          },
        },
      })
      .catch(() => {});
  }

  async webhookError(command: SlashCommand, error: Error) {
    await this.client.req
      .webhooks(this.client.user.id)(command.token)
      .post({
        data: {
          content: `${emojis.error} An error occured while trying to handle this command that may be caused by being in DMs or the bot not being present...

Try inviting the bot (<${this.client.config.inviteLink}>) and try again.

Error Message: ${error.message}`,
        },
      })
      .catch(() => {});
  }
}
