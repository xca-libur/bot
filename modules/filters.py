"""
MIT License
Copyright (c) 2020 GamingGeek

Permission is hereby granted, free of charge, to any person obtaining a copy of this software
and associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


from fire.filters.youtube import findchannel, findvideo
from fire.filters.twitter import findtwitter
from fire.filters.shorten import findshort
from fire.filters.invite import findinvite
from fire.filters.paypal import findpaypal
from fire.filters.twitch import findtwitch
from fire.filters.gift import findgift
from fire.filters.sku import findsku
from discord.ext import commands
import functools
import datetime
import aiohttp
import discord


class Filters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.imgext = ['.png', '.jpg', '.gif']
        self.malware = []
        self.blocked_gifts = [gift for gift in open('blocked_gifts.txt').read().split('\n') if gift]
        self.allowed_invites = [inv for inv in open('allowed_invites.txt').read().split('\n') if inv]
        self.bot.loop.create_task(self.get_malware())

    async def get_malware(self):
        try:
            async with aiohttp.ClientSession() as s:
                malware = await (await s.get('https://mirror.cedia.org.ec/malwaredomains/justdomains')).text()
                await s.close()
            self.malware = list(filter(None, malware.split('\n')))
        except Exception as e:
            self.bot.logger.error(f'$REDFailed to fetch malware domains', exc_info=e)

    async def safe_exc(self, coro, *args, **kwargs):
        try:
            await coro(*args, **kwargs)
        except Exception as e:
            pass

    async def run_all(self, message, extra: str = '', exclude: list = []):  # Some filters may uncover extra content (e.g. gift metadata) and rerun all filters with that data
        if message.author.bot:  # Somehow this STILL gets triggered by bot messages
            return
        if 'discord' not in exclude:
            await self.safe_exc(self.handle_invite, message, extra)
        if 'malware' not in exclude:
            await self.safe_exc(self.anti_malware, message, extra)
        if 'paypal' not in exclude:
            await self.safe_exc(self.handle_paypal, message, extra)
        if 'youtube' not in exclude:
            await self.safe_exc(self.handle_youtube, message, extra)
        if 'twitch' not in exclude:
            await self.safe_exc(self.handle_twitch, message, extra)
        if 'twitter' not in exclude:
            await self.safe_exc(self.handle_twitter, message, extra)
        if 'shorteners' not in exclude:
            await self.safe_exc(self.handle_shorturl, message, extra)
        if 'gift' not in exclude:
            await self.safe_exc(self.handle_gift, message, extra)
        if 'sku' not in exclude:
            await self.safe_exc(self.handle_sku, message, extra)

    async def handle_invite(self, message, extra):
        tosearch = str(message.system_content) + str([e.to_dict() for e in message.embeds]) if not extra else extra
        codes = findinvite(tosearch)
        invite = None
        for fullurl, code in codes:
            if fullurl in self.allowed_invites:
                continue
            if any(u in fullurl for u in ['h.inv.wtf', 'i.inv.wtf']) and self.bot.isadmin(message.author):
                continue
            if not message.author.permissions_in(message.channel).manage_messages:
                if 'discord' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                    try:
                        invite = await self.bot.fetch_invite(url=code)
                        if invite.guild.id != message.guild.id:
                            await message.delete()
                    except discord.NotFound:
                        vanitydomains = ['oh-my-god.wtf', 'inv.wtf', 'floating-through.space', 'i-live-in.space', 'i-need-personal.space', 'get-out-of-my-parking.space']
                        if any(d in fullurl for d in vanitydomains):
                            invite = await self.bot.get_vanity(code)
                            if not invite or invite['gid'] != message.guild.id:
                                try:
                                    await message.delete()
                                except Exception:
                                    pass
                        else:
                            try:
                                await message.delete()
                            except Exception:
                                pass
                    except discord.Forbidden:
                        pass
                    logch = await self.bot.get_config(message.guild).get('log.action')
                    if logch:
                        description = f'**Invite link sent in** {message.channel.mention}'
                        if fullurl in extra:
                            if fullurl in str(message.system_content) + str([e.to_dict() for e in message.embeds]):  # Prevent logging inf also in content/embed
                                continue
                            description = f'**Invite link found in external content**'
                        embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=description)
                        embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                        embed.add_field(name='Invite Code', value=code, inline=False)
                        if isinstance(invite, dict):
                            invite = await self.bot.fetch_invite(url=invite['invite'])
                        if isinstance(invite, discord.Invite):
                            embed.add_field(name='Guild', value=f'{invite.guild.name}({invite.guild.id})', inline=False)
                            embed.add_field(name='Channel', value=f'#{invite.channel.name}({invite.channel.id})', inline=False)
                            embed.add_field(name='Members', value=f'{invite.approximate_member_count} ({invite.approximate_presence_count} active)', inline=False)
                        embed.set_footer(text=f"Author ID: {message.author.id}")
                        try:
                            await logch.send(embed=embed)
                        except Exception:
                            pass

    async def anti_malware(self, message, extra):  # Get it? It gets rid of malware links so it's, anti malware. I'm hilarious!
        tosearch = str(message.system_content) + str([e.to_dict() for e in message.embeds]) if not extra else extra
        if any(l in tosearch for l in self.malware):
            if 'malware' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                try:
                    await message.delete()
                except Exception:
                    try:
                        await message.channel.send(f'A blacklisted link was found in a message send by {message.author} and I was unable to delete it!')
                    except Exception:
                        pass
                logch = await self.bot.get_config(message.guild).get('log.action')
                if logch:
                    description = f'**Known malware link sent in** {message.channel.mention}'
                    if any(l in extra for l in self.malware):
                        if any(l in str(message.system_content) + str([e.to_dict() for e in message.embeds]) for l in self.malware):
                            return
                        description = f'**Known malware link found in external content**'
                    embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=description)
                    embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                    embed.set_footer(text=f"Author ID: {message.author.id}")
                    try:
                        await logch.send(embed=embed)
                    except Exception:
                        pass

    async def handle_paypal(self, message, extra):
        tosearch = str(message.system_content) + str([e.to_dict() for e in message.embeds]) if not extra else extra
        paypal = findpaypal(tosearch)
        if paypal:
            if not message.author.permissions_in(message.channel).manage_messages:
                if 'paypal' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    logch = await self.bot.get_config(message.guild).get('log.action')
                    if logch:
                        description = f'**PayPal link sent in** {message.channel.mention}'
                        if paypal in extra:
                            if paypal in str(message.system_content) + str([e.to_dict() for e in message.embeds]):
                                return
                            description = f'**PayPal link found in external content**'
                        embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=description)
                        embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                        embed.add_field(name='Link', value=f'[{paypal}](https://paypal.me/{paypal})', inline=False)
                        embed.set_footer(text=f"Author ID: {message.author.id}")
                        try:
                            await logch.send(embed=embed)
                        except Exception:
                            pass

    async def handle_youtube(self, message, extra):
        ytcog = self.bot.get_cog('YouTube API')
        tosearch = str(message.system_content) + str([e.to_dict() for e in message.embeds]) if not extra else extra
        video = findvideo(tosearch)
        channel = findchannel(tosearch)
        invalidvid = False
        invalidchannel = False
        if video:
            if not message.author.permissions_in(message.channel).manage_messages:
                if 'youtube' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    videoinfo = await self.bot.loop.run_in_executor(None, func=functools.partial(ytcog.video_info, video))
                    videoinfo = videoinfo.get('items', [])
                    if len(videoinfo) >= 1:
                        videoinfo = videoinfo[0]
                        logch = await self.bot.get_config(message.guild).get('log.action')
                        if logch:
                            description = f'**YouTube video sent in** {message.channel.mention}'
                            if video in extra:
                                if video in str(message.system_content) + str([e.to_dict() for e in message.embeds]):
                                    return
                                description = f'**YouTube video found in external content**'
                            embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=description)
                            embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                            embed.add_field(name='Video ID', value=video, inline=False)
                            if not invalidvid:
                                embed.add_field(name='Title', value=f'[{videoinfo.get("snippet", {}).get("title", "Unknown")}](https://youtu.be/{video})', inline=False)
                                embed.add_field(name='Channel', value=f'[{videoinfo.get("snippet", {}).get("channelTitle", "Unknown")}](https://youtube.com/channel/{videoinfo.get("snippet", {}).get("channelId", "Unknown")})', inline=False)
                                views = format(int(videoinfo['statistics'].get('viewCount', 0)), ',d')
                                likes = format(int(videoinfo['statistics'].get('likeCount', 0)), ',d')
                                dislikes = format(int(videoinfo['statistics'].get('dislikeCount', 0)), ',d')
                                comments = format(int(videoinfo['statistics'].get('commentCount', 0)), ',d')
                                embed.add_field(name='Stats', value=f'{views} views, {likes} likes, {dislikes} dislikes, {comments} comments', inline=False)
                            embed.set_footer(text=f"Author ID: {message.author.id}")
                            try:
                                await logch.send(embed=embed)
                            except Exception:
                                pass
        if channel:
            if not message.author.permissions_in(message.channel).manage_messages:
                if 'youtube' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    channelinfo = await self.bot.loop.run_in_executor(None, func=functools.partial(ytcog.channel_info, channel))
                    channelinfo = channelinfo.get('items', [])
                    if len(channelinfo) >= 1:
                        channelinfo = channelinfo[0]
                        logch = await self.bot.get_config(message.guild).get('log.action')
                        if logch:
                            description = f'**YouTube channel sent in** {message.channel.mention}'
                            if channel in extra:
                                if channel in str(message.system_content) + str([e.to_dict() for e in message.embeds]):
                                    return
                                description = f'**YouTube channel found in external content**'
                            embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=description)
                            embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                            if not invalidchannel:
                                embed.add_field(name='Name', value=f'{channelinfo.get("snippet", {}).get("title", "Unknown")}', inline=False)
                                embed.add_field(name='Channel', value=f'https://youtube.com/channel/{channel}')
                                embed.add_field(name='Custom URL', value=f'https://youtube.com/{channelinfo.get("snippet", {}).get("customUrl", "N/A")}', inline=False)
                                subs = format(int(channelinfo['statistics'].get('subscriberCount', 0)), ',d') if not channelinfo['statistics'].get('hiddenSubscriberCount', False) else 'Hidden'
                                views = format(int(channelinfo['statistics'].get('viewCount', 0)), ',d')
                                videos = format(int(channelinfo['statistics'].get('videoCount', 0)), ',d')
                                embed.add_field(name='Stats', value=f'{subs} subscribers, {views} total views, {videos} videos', inline=False)
                            embed.set_footer(text=f"Author ID: {message.author.id}")
                            try:
                                await logch.send(embed=embed)
                            except Exception:
                                pass

    async def handle_twitch(self, message, extra):
        tosearch = str(message.system_content) + str([e.to_dict() for e in message.embeds]) if not extra else extra
        twitch = findtwitch(tosearch)
        if twitch:
            if not message.author.permissions_in(message.channel).manage_messages:
                if 'twitch' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    logch = await self.bot.get_config(message.guild).get('log.action')
                    if logch:
                        description = f'**Twitch link sent in** {message.channel.mention}'
                        if twitch in extra:
                            if twitch in str(message.system_content) + str([e.to_dict() for e in message.embeds]):
                                return
                            description = f'**Twitch link found in external content**'
                        embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=description)
                        embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                        embed.add_field(name='Link', value=f'[{twitch}](https://twitch.tv/{twitch})', inline=False)
                        embed.set_footer(text=f"Author ID: {message.author.id}")
                        try:
                            await logch.send(embed=embed)
                        except Exception:
                            pass

    async def handle_twitter(self, message, extra):
        tosearch = str(message.system_content) + str([e.to_dict() for e in message.embeds]) if not extra else extra
        twitter = findtwitter(tosearch)
        if twitter:
            if not message.author.permissions_in(message.channel).manage_messages:
                if 'twitter' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    logch = await self.bot.get_config(message.guild).get('log.action')
                    if logch:
                        description = f'**Twitter link sent in** {message.channel.mention}'
                        if twitter in extra:
                            if twitter in str(message.system_content) + str([e.to_dict() for e in message.embeds]):
                                return
                            description = f'**Twitter link found in external content**'
                        embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=description)
                        embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                        embed.add_field(name='Link', value=f'[{twitter}](https://twitter.com/{twitter})', inline=False)
                        embed.set_footer(text=f"Author ID: {message.author.id}")
                        try:
                            await logch.send(embed=embed)
                        except Exception:
                            pass

    async def handle_shorturl(self, message, extra):
        tosearch = str(message.system_content) + str([e.to_dict() for e in message.embeds]) if not extra else extra
        short = findshort(tosearch)
        if short:
            if not message.author.permissions_in(message.channel).manage_messages:
                if 'shorteners' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    logch = await self.bot.get_config(message.guild).get('log.action')
                    if logch:
                        description = f'**Short link sent in** {message.channel.mention}'
                        if short in extra:
                            if short in str(message.system_content) + str([e.to_dict() for e in message.embeds]):
                                return
                            description = f'**Short link found in external content**'
                        embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=f'**Short link sent in** {message.channel.mention}')
                        embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                        embed.add_field(name='Link', value=short, inline=False)
                        embed.set_footer(text=f"Author ID: {message.author.id}")
                        try:
                            await logch.send(embed=embed)
                        except Exception:
                            pass

    async def handle_gift(self, message, extra):
        tosearch = str(message.system_content) + str([e.to_dict() for e in message.embeds]) if not extra else extra
        codes = findgift(tosearch)
        gift = None
        for fullurl, code in codes:
            try:
                gift = await self.bot.http.request(discord.http.Route("GET", f"/entitlements/gift-codes/{code}?with_application=true&with_subscription_plan=true"))
            except discord.HTTPException:
                continue
            if gift:
                await self.run_all(message, extra=str(gift) + 'handle_gift', exclude=['gift'])
            logch = await self.bot.get_config(message.guild).get('log.action')
            if not logch:
                continue
            if gift['application_id'] in ['521842831262875670']:
                embed = discord.Embed(color=discord.Color.from_rgb(197, 126, 217), timestamp=message.created_at, description=f'**Nitro gift sent in** {message.channel.mention}')
                embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                embed.add_field(name='Type', value=gift['subscription_plan']['name'], inline=False)
                embed.add_field(name='Redeemed', value='Yes' if gift['uses'] == gift['max_uses'] else 'Nope', inline=False)
                embed.set_footer(text=f"Author ID: {message.author.id}")
                try:
                    await logch.send(embed=embed)
                except Exception:
                    pass
                gift = None
                continue
            if gift['application_id'] in self.blocked_gifts:
                if 'gifts' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                    if not message.author.permissions_in(message.channel).manage_messages:
                        try:
                            await message.delete()
                        except Exception:
                            pass
                        embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=f'**Blocked gift sent in** {message.channel.mention}')
                        embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                        embed.add_field(name='Link', value=fullurl, inline=False)
                        embed.set_footer(text=f"Author ID: {message.author.id}")
                        try:
                            await logch.send(embed=embed)
                        except Exception:
                            pass
                        gift = None
                        continue
            embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=f'**Game gift sent in** {message.channel.mention}')
            embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
            embed.add_field(name='Name', value=gift['store_listing']['sku']['name'], inline=False)
            embed.add_field(name='Tagline', value=gift['store_listing']['tagline'], inline=False)
            embed.add_field(name='Redeemed', value='Yes' if gift['uses'] == gift['max_uses'] else 'Nope', inline=False)
            embed.set_footer(text=f"Author ID: {message.author.id}")
            try:
                await logch.send(embed=embed)
            except Exception:
                pass
            gift = None

    async def handle_sku(self, message, extra):
        tosearch = str(message.system_content) + str([e.to_dict() for e in message.embeds]) if not extra else extra
        codes = findsku(tosearch)
        sku = None
        for fullurl, code in codes:
            try:
                sku = await self.bot.http.request(discord.http.Route("GET", f"/store/published-listings/skus/{code}"))
            except discord.HTTPException:
                continue
            if sku:
                sku.pop('summary', None) # prevent duped logs since summary is already in the embed description
                await self.run_all(message, extra=str(sku), exclude=['sku'])
            logch = await self.bot.get_config(message.guild).get('log.action')
            if not logch:
                continue
            if sku['sku']['application_id'] in self.blocked_gifts:
                if 'gifts' in (await self.bot.get_config(message.guild).get('mod.linkfilter')):
                    if not message.author.permissions_in(message.channel).manage_messages:
                        try:
                            await message.delete()
                        except Exception:
                            pass
                        embed = discord.Embed(color=message.author.color, timestamp=message.created_at, description=f'**Blocked gift sent in** {message.channel.mention}')
                        embed.set_author(name=message.author, icon_url=str(message.author.avatar_url_as(static_format='png', size=2048)))
                        embed.add_field(name='Link', value=fullurl, inline=False)
                        embed.set_footer(text=f"Author ID: {message.author.id}")
                        try:
                            await logch.send(embed=embed)
                        except Exception:
                            pass
                        sku = None
                        continue



def setup(bot):
    bot.add_cog(Filters(bot))
    bot.logger.info(f'$GREENLoaded $CYANFilters $GREENmodule!')
