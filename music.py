import discord
from discord.ext import commands
import yt_dlp
import asyncio
import json
import os
from ..utils.music_utils import MusicControlView, get_channel_data, ydl_opts

def save_song(url: str, title: str):
    json_path = os.path.join(os.path.dirname(__file__), '../utils/songs.json')
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"songs": []}

    song_exists = False
    for song in data["songs"]:
        if song["url"] == url:
            song_exists = True
            break

    if not song_exists:
        data["songs"].append({"title": title, "url": url})
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sp = bot.sp
        self.inactivity_tasks = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel and not member.bot:
            channel_id = before.channel.id
            guild_data = get_channel_data(member.guild.id, channel_id)

            # Vérifie si le bot est dans ce salon
            if guild_data['voice_clients'][channel_id]:
                # Compte les membres non-bots dans le salon
                members = len([m for m in before.channel.members if not m.bot])

                # Si plus personne dans le salon
                if members == 0:
                    await guild_data['voice_clients'][channel_id].disconnect()
                    guild_data['voice_clients'][channel_id] = None
                    guild_data['queues'][channel_id] = []
                    guild_data['is_playing'][channel_id] = False

    @discord.app_commands.command(name="play", description="Joue une musique depuis YouTube ou Spotify")
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("❌ Vous devez être dans un salon vocal!", ephemeral=True)
            return

        channel_id = interaction.user.voice.channel.id
        guild_data = get_channel_data(interaction.guild_id, channel_id)

        if "spotify.com" in url:
            try:
                track_id = url.split("/")[-1].split("?")[0]
                track = self.sp.track(track_id)
                search_query = f"{track['name']} {track['artists'][0]['name']}"
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(f"ytsearch:{search_query}", download=False)
                    if 'entries' in result and result['entries']:
                        url = result['entries'][0]['url']
                    else:
                        await interaction.followup.send("❌ Aucun résultat trouvé pour cette musique", ephemeral=True)
                        return
            except Exception as e:
                await interaction.followup.send(f"❌ Erreur avec le lien Spotify: {str(e)}", ephemeral=True)
                return

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            save_song(url, info['title'])
            guild_data['queues'][channel_id].append(url)

        if not guild_data['is_playing'][channel_id]:
            await self.play_next(interaction, channel_id)
            await interaction.followup.send("▶️ Lecture démarrée!", ephemeral=True)
        else:
            await interaction.followup.send("➕ Musique ajoutée à la file!", ephemeral=True)

    async def play_next(self, interaction, channel_id):
        guild_data = get_channel_data(interaction.guild_id, channel_id)
        guild_data['is_playing'][channel_id] = False

        if not guild_data['queues'][channel_id]:
            if guild_data['controls_messages'][channel_id]:
                try:
                    await guild_data['controls_messages'][channel_id].edit(view=None)
                except discord.NotFound:
                    pass
                return

        song_url = guild_data['queues'][channel_id].pop(0)
        guild_data['is_playing'][channel_id] = True

        if not guild_data['voice_clients'][channel_id]:
            if interaction.user.voice:
                channel = interaction.user.voice.channel
                guild_data['voice_clients'][channel_id] = await channel.connect()

        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(song_url, download=False)
                url2 = info['url']
                source = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)
            except Exception as e:
                print(f"Erreur avec le format principal, tentative avec format alternatif: {str(e)}")
                # Essai avec un format alternatif
                try:
                    ydl.params['format'] = 'worstaudio/worst'
                    info = ydl.extract_info(song_url, download=False)
                    url2 = info['url']
                    source = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)
                except Exception as e2:
                    print(f"Erreur avec le format alternatif: {str(e2)}")
                    await interaction.channel.send("❌ Impossible de lire cette musique - Protection anti-bot détectée")
                    return None

            embed = discord.Embed(
                title="🎵 Musique en cours",
                description=f"**{info['title']}**",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=info.get('thumbnail'))
            embed.add_field(name="Durée", value=f"{int(info['duration']/60)}:{int(info['duration']%60):02d}")

            if guild_data['controls_messages'][channel_id]:
                try:
                    await guild_data['controls_messages'][channel_id].edit(view=None)
                except discord.NotFound:
                    pass

            guild_data['controls_messages'][channel_id] = await interaction.channel.send(
                embed=embed, 
                view=MusicControlView(channel_id)
            )

        def after_playing(error):
            if error:
                print(f"Erreur de lecture : {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(interaction, channel_id), self.bot.loop)

        if channel_id in self.inactivity_tasks and self.inactivity_tasks[channel_id]:
            self.inactivity_tasks[channel_id].cancel()

        async def check_inactivity():
            await asyncio.sleep(20)
            if guild_data['voice_clients'][channel_id]:
                if not guild_data['voice_clients'][channel_id].is_playing():
                    await guild_data['voice_clients'][channel_id].disconnect()
                    guild_data['voice_clients'][channel_id] = None
                    guild_data['queues'][channel_id] = []
                    guild_data['is_playing'][channel_id] = False

        self.inactivity_tasks[channel_id] = asyncio.create_task(check_inactivity())
        guild_data['voice_clients'][channel_id].play(source, after=after_playing)

    @discord.app_commands.command(name="leave", description="Déconnecte le bot du salon vocal")
    async def leave(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Vous devez être dans un salon vocal!", ephemeral=True)
            return

        channel_id = interaction.user.voice.channel.id
        guild_data = get_channel_data(interaction.guild_id, channel_id)

        # Vérifie si le bot est dans le salon vocal de l'utilisateur
        if guild_data['voice_clients'][channel_id]:
            await guild_data['voice_clients'][channel_id].disconnect()
            guild_data['voice_clients'][channel_id] = None
            guild_data['queues'][channel_id] = []
            guild_data['is_playing'][channel_id] = False

            # Nettoie les tâches d'inactivité
            if channel_id in self.inactivity_tasks and self.inactivity_tasks[channel_id]:
                self.inactivity_tasks[channel_id].cancel()
                del self.inactivity_tasks[channel_id]

            await interaction.response.send_message("👋 Bot déconnecté!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Bot non connecté à ce salon vocal", ephemeral=True)

    @discord.app_commands.command(name="queue", description="Affiche la file d'attente")
    async def queue(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Vous devez être dans un salon vocal!", ephemeral=True)
            return

        channel_id = interaction.user.voice.channel.id
        guild_data = get_channel_data(interaction.guild_id, channel_id)

        if not guild_data['queues'][channel_id]:
            await interaction.response.send_message("📝 La file d'attente est vide!", ephemeral=True)
            return

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            queue_list = []
            for i, url in enumerate(guild_data['queues'][channel_id], 1):
                info = ydl.extract_info(url, download=False)
                queue_list.append(f"{i}. {info['title']}")

        embed = discord.Embed(
            title="📝 File d'attente",
            description="\n".join(queue_list),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Music(bot))