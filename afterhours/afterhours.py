"""After hours module.

A special cog to handle the special cases for this channel.
"""
import logging
from datetime import datetime, timedelta
import asyncio
import discord
from discord.ext import commands
from redbot.core import Config, checks, commands, data_manager
from redbot.core.bot import Red
from redbot.core.commands.context import Context

# Basic constants
AH_CHANNEL = "after-hours"
KEY_CTX_CHANNEL_ID = "channelId"
KEY_CHANNEL_IDS = "channelIds"
KEY_ROLE_ID = "roleId"
DEFAULT_GUILD = {KEY_CTX_CHANNEL_ID: None, KEY_CHANNEL_IDS: {}, KEY_ROLE_ID: None}
STARBOARD = "highlights"
DELETE_TIME = 32 * 60 * 60
SLEEP_TIME = 60 * 60


# Logging
KEY_LAST_MSG_TIMESTAMPS = "lastMsgTimestamps"

# Auto-purging
KEY_AUTO_PURGE = "autoPurge"
KEY_INACTIVE_DURATION = "inactiveDuration"
KEY_INACTIVE_DURATION_YEARS = "inactiveDurationYears"
KEY_INACTIVE_DURATION_MONTHS = "inactiveDurationMonths"
KEY_INACTIVE_DURATION_WEEKS = "inactiveDurationWeeks"
KEY_INACTIVE_DURATION_DAYS = "inactiveDurationDays"
KEY_INACTIVE_DURATION_HOURS = "inactiveDurationHours"
KEY_INACTIVE_DURATION_MINUTES = "inactiveDurationMinutes"
KEY_INACTIVE_DURATION_SECONDS = "inactiveDurationSeconds"

# Default guild settings
DEFAULT_GUILD = {
    KEY_CTX_CHANNEL_ID: None,
    KEY_CHANNEL_IDS: {},
    KEY_ROLE_ID: None,
    KEY_LAST_MSG_TIMESTAMPS: {},
    KEY_AUTO_PURGE: {
        KEY_INACTIVE_DURATION: {
            KEY_INACTIVE_DURATION_YEARS: 0,
            KEY_INACTIVE_DURATION_MONTHS: 0,
            KEY_INACTIVE_DURATION_WEEKS: 0,
            KEY_INACTIVE_DURATION_DAYS: 0,
            KEY_INACTIVE_DURATION_HOURS: 0,
            KEY_INACTIVE_DURATION_MINUTES: 0,
            KEY_INACTIVE_DURATION_SECONDS: 0,
        },
    },
}


class AfterHours(commands.Cog):
    """Special casing galore!"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=5842647, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)

        # Initialize logger, and save to cog folder.
        saveFolder = data_manager.cog_data_path(cog_instance=self)
        self.logger = logging.getLogger("red.luicogs.AfterHours")
        if self.logger.level == 0:
            # Prevents the self.logger from being loaded again in case of module reload.
            self.logger.setLevel(logging.INFO)
            handler = logging.FileHandler(
                filename=str(saveFolder) + "/info.log", encoding="utf-8", mode="a"
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(message)s", datefmt="[%d/%m/%Y %H:%M:%S]")
            )
            self.logger.addHandler(handler)
        self.bgTask = self.bot.loop.create_task(self.backgroundLoop())

    # Cancel the background task on cog unload.
    def __unload(self):  # pylint: disable=invalid-name
        self.logger.info("Unloading cog")
        self.bgTask.cancel()

    def cog_unload(self):
        self.logger.info("Unloading cog")
        self.__unload()

    async def backgroundLoop(self):
        """Background loop to garbage collect"""
        while True:
            self.logger.debug("Checking to see if we need to garbage collect")
            for guild in self.bot.guilds:
                self.logger.debug("Checking guild %s", guild.id)
                async with self.config.guild(guild).get_attr(KEY_CHANNEL_IDS)() as channels:
                    staleIds = []
                    for channelId, data in channels.items():
                        self.logger.debug("Checking channel ID %s", channelId)
                        channel = discord.utils.get(guild.channels, id=int(channelId))
                        if not channel:
                            self.logger.error("Channel ID %s doesn't exist!", channelId)
                            staleIds.append(channelId)
                            continue
                        creationTime = datetime.fromtimestamp(data["time"])
                        self.logger.debug("Time difference = %s", datetime.now() - creationTime)
                        if datetime.now() - creationTime > timedelta(seconds=DELETE_TIME):
                            self.logger.info("Deleting channel %s (%s)", channel.name, channel.id)
                            await channel.delete(reason="AfterHours purge")
                            # Don't delete the ID here, this will be taken care of in
                            # the delete listener
                    for channelId in staleIds:
                        self.logger.info("Purging stale channel ID %s", channelId)
                        del channels[channelId]
            await asyncio.sleep(SLEEP_TIME)

    async def getContext(self, channel: discord.TextChannel):
        """Get the Context object from a text channel.

        Parameters
        ----------
        channel: discord.TextChannel
            The text channel to use in order to create the Context object.

        Returns
        -------
        ctx: Context
            The context needed to send messages and invoke methods from other cogs.
        """
        ctxGuild = channel.guild
        ctxChannelId = await self.config.guild(ctxGuild).get_attr(KEY_CTX_CHANNEL_ID)()
        ctxChannel = discord.utils.get(ctxGuild.channels, id=ctxChannelId)
        if not ctxChannel:
            self.logger.error("Cannot find channel to construct context!")
            return None
        async for message in ctxChannel.history(limit=1):
            lastMessage = message
        return await self.bot.get_context(lastMessage)

    async def makeStarboardChanges(
        self, ctx: Context, channel: discord.abc.GuildChannel, remove=False
    ):
        """Apply Starboard changes.

        Parameters
        -----------
        ctx: Context
            The Context object in order to invoke commands
        channel: discord.abc.GuildChannel
            The channel to apply Starboard changes to.
        remove: bool
            Indicate whether we want to remove the changes. Defaults to False.
        """
        self.logger.info("Applying/removing Starboard exceptions, remove=%s", remove)
        sbCog = self.bot.get_cog("Starboard")
        if not sbCog:
            self.logger.error("Starboard not loaded. skipping")
            return

        try:
            starboard = sbCog.starboards[ctx.guild.id]["highlights"]
        except KeyError:
            self.logger.error("Cannot get the starboard!")

        if remove:
            await ctx.invoke(sbCog.blacklist_remove, starboard=starboard, channel_or_role=channel)
        else:
            await ctx.invoke(sbCog.blacklist_add, starboard=starboard, channel_or_role=channel)

    async def notifyChannel(self, ctx, remove=False):
        if remove:
            await ctx.send(f":information_source: **{AH_CHANNEL} removed, removing exceptions**")
        else:
            await ctx.send(f":information_source: **{AH_CHANNEL} created, adding exceptions**")

    async def makeWordFilterChanges(
        self, ctx: Context, channel: discord.abc.GuildChannel, remove=False
    ):
        """Apply WordFilter changes.

        Parameters
        -----------
        ctx: Context
            The Context object in order to invoke commands
        channel: discord.abc.GuildChannel
            The channel to apply WordFilter changes to.
        remove: bool
            Indicate whether we want to remove the changes. Defaults to False.
        """
        self.logger.info("Applying/removing WordFilter exceptions, remove=%s", remove)
        cog = self.bot.get_cog("WordFilter")
        if not cog:
            self.logger.error("WordFilter not loaded. skipping")
            return

        if remove:
            await ctx.invoke(cog._channelRemove, channel=channel)
        else:
            await ctx.invoke(cog._channelAdd, channel=channel)

    @commands.Cog.listener("on_guild_channel_create")
    async def handleChannelCreate(self, channel: discord.abc.GuildChannel):
        """Listener to see if we need to add exceptions to a channel"""
        self.logger.info(
            "Channel creation has been detected. Name: %s, ID: %s", channel.name, channel.id
        )

        if not isinstance(channel, discord.TextChannel):
            return

        if channel.name == AH_CHANNEL:
            self.logger.info("%s detected, applying exceptions", AH_CHANNEL)
            ctx = await self.getContext(channel)
            if not ctx:
                return
            await self.notifyChannel(ctx)
            await self.makeStarboardChanges(ctx, channel)
            await self.makeWordFilterChanges(ctx, channel)
            async with self.config.guild(channel.guild).get_attr(KEY_CHANNEL_IDS)() as channelIds:
                channelIds[channel.id] = {"time": datetime.now().timestamp()}

    @commands.Cog.listener("on_guild_channel_delete")
    async def handleChannelDelete(self, channel: discord.abc.GuildChannel):
        """Listener to see if we need to remove exceptions from a channel"""
        self.logger.info(
            "Channel deletion has been detected. Name: %s, ID: %s", channel.name, channel.id
        )

        if not isinstance(channel, discord.TextChannel):
            return

        async with self.config.guild(channel.guild).get_attr(KEY_CHANNEL_IDS)() as channelIds:
            if str(channel.id) in channelIds:
                self.logger.info("%s detected, removing exceptions", AH_CHANNEL)
                ctx = await self.getContext(channel)
                if not ctx:
                    return
                await self.notifyChannel(ctx, remove=True)
                await self.makeStarboardChanges(ctx, channel, remove=True)
                await self.makeWordFilterChanges(ctx, channel, remove=True)
                del channelIds[str(channel.id)]

    @commands.group(name="afterhours")
    @commands.guild_only()
    async def afterHours(self, ctx: Context):
        """Manage after-hours"""

    @checks.mod_or_permissions(manage_messages=True)
    @afterHours.command(name="setrole")
    async def afterHoursSetRole(self, ctx: Context, role: discord.Role):
        """Set the after-hours role.

        This allows for self-removals later.

        Parameters
        ----------
        role: discord.Role
            The role associated with after hours.
        """
        await self.config.guild(ctx.guild).get_attr(KEY_ROLE_ID).set(role.id)
        await ctx.send(f"Set the After Hours role to {role.name}")

    @afterHours.command(name="removerole")
    async def afterHoursRemoveRole(self, ctx: Context):
        """Remove the after-hours role from yourself."""
        # check if after hours role is set
        roleid = await self.config.guild(ctx.guild).get_attr(KEY_ROLE_ID)()
        if roleid is None:
            await ctx.send("Please configure the after-hours role first!")
            return
        # get after hours role by id
        role = ctx.guild.get_role(roleid)
        # if id is no longer valid (role deleted most likely)
        if role is None:
            await ctx.send(
                "After Hours role no longer valid, most likely role was deleted by admins"
            )
            return

        # check if user has roles
        rolesList = ctx.author.roles
        if role not in rolesList:
            await ctx.send(f"You do not have the role {role.name}")
            return
        # remove role
        try:
            await ctx.author.remove_roles(role, reason="User removed role")
        except discord.Forbidden:
            self.logger.error("Not allowed to remove role", exc_info=True)
        except discord.HTTPException:
            self.logger.error("HTTP Exception", exc_info=True)

        # post message saying role removed
        await ctx.send(f"Removed the role {role.name} from you.")

    @checks.mod_or_permissions(manage_messages=True)
    @afterHours.command(name="setchannel")
    async def afterHoursSet(self, ctx: Context):
        """Set the channel for notifications."""
        await self.config.guild(ctx.guild).get_attr(KEY_CTX_CHANNEL_ID).set(ctx.channel.id)
        await ctx.send("Using this channel to construct context later!")
