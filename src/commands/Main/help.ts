import { titleCase, constants } from "@fire/lib/util/constants";
import { FireMessage } from "@fire/lib/extensions/message";
import { Language } from "@fire/lib/util/language";
import { Command } from "@fire/lib/util/command";
import { PermissionString } from "discord.js";

export default class Help extends Command {
  constructor() {
    super("help", {
      description: (language: Language) =>
        language.get("HELP_COMMAND_DESCRIPTION"),
      clientPermissions: ["EMBED_LINKS", "SEND_MESSAGES"],
      aliases: ["helpme", "commands", "h"],
      args: [
        {
          id: "command",
          type: "command",
          default: undefined,
          required: false,
        },
      ],
      enableSlashCommand: true,
      restrictTo: "all",
    });
  }

  async exec(message: FireMessage, args: { command: Command }) {
    if (typeof args.command == "undefined") return await this.sendHelp(message);
    else if (!args.command) return await message.error("HELP_NO_COMMAND");
    else return await this.sendUsage(message, args.command);
  }

  async sendHelp(message: FireMessage) {
    let fields: { name: string; value: string; inline: boolean }[] = [];
    for (const [name, category] of this.client.commandHandler.categories) {
      if (name == "Admin" && !message.author.isSuperuser()) continue;
      let commands: string[] = [];
      category
        .filter((command) => {
          if (command.ownerOnly && this.client.ownerID != message.author.id)
            return false;
          if (command.superuserOnly && !message.author.isSuperuser())
            return false;
          if (
            command.moderatorOnly &&
            !message.member?.isModerator(message.channel)
          )
            return false;
          if (
            command.guilds.length &&
            !command.guilds.includes(message.guild?.id)
          )
            return false;
          if (command.channel == "guild" && !message.guild) return false;
          return true;
        })
        .forEach((command) => commands.push(`\`${command.id}\``));
      if (commands.length)
        fields.push({
          name: category.id,
          value: commands.join(", "),
          inline: false,
        });
    }
    const embed = {
      color: message.member?.displayHexColor || "#ffffff",
      author: {
        icon_url: this.client.user.displayAvatarURL({
          size: 2048,
          format: "png",
        }),
      },
      fields,
      footer: {
        text: message.language.get(
          "HELP_FOOTER",
          message.util.parsed.prefix.replace(
            this.client.user.toString(),
            `@${this.client.user.username} `
          ) || "$",
          this.client.manager.id
        ) as string,
      },
      timestamp: new Date(),
    };
    await message.channel.send({ embed });
  }

  async sendUsage(message: FireMessage, command: Command) {
    let permissions: string[] = [];
    ((command.userPermissions || []) as Array<string>).forEach(
      (perm: string) => {
        permissions.push(
          this.client.util.cleanPermissionName(perm as PermissionString)
        );
      }
    );
    let args: string[] = command.getArgumentsClean();
    const embed = {
      color: message.member?.displayHexColor || "#ffffff",
      title: titleCase(command.id),
      description: command.description(message.language),
      fields: [
        {
          name: "» Usage",
          value: `${message.util.parsed.prefix || "$"}${command.id} ${
            args?.join(" ").replace(/\] \[/gim, " ") || ""
          }`,
          inline: false,
        },
      ],
      timestamp: new Date(),
    };
    if (permissions.length)
      embed.fields.push({
        name: "» Permission" + (permissions.length > 1 ? "s" : ""),
        value: permissions.join(", "),
        inline: false,
      });
    await message.channel.send({ embed });
  }
}
