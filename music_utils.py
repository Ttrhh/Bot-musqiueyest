
import discord

guild_data = {}

def get_guild_data(guild_id):
    if guild_id not in guild_data:
        guild_data[guild_id] = {
            'voice_clients': {},  # Changed to support multiple voice channels
            'queues': {},        # Changed to support multiple voice channels
            'is_playing': {},    # Changed to support multiple voice channels
            'controls_messages': {}  # Changed to support multiple voice channels
        }
    return guild_data[guild_id]

def get_channel_data(guild_id, channel_id):
    guild = get_guild_data(guild_id)
    if channel_id not in guild['voice_clients']:
        guild['voice_clients'][channel_id] = None
        guild['queues'][channel_id] = []
        guild['is_playing'][channel_id] = False
        guild['controls_messages'][channel_id] = None
    return guild

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'extractor_retries': 5,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36'
    },
    'extractors': ['youtube', 'soundcloud', 'bandcamp', 'vimeo', 'twitch:stream'],
    'extractor_args': {
        'youtube': {
            'skip_dash_manifest': True,
            'nocheckcertificate': True
        }
    },
    'extract_flat': 'in_playlist',
    'concurrent_fragment_downloads': 1,
    'retries': 10,
    'file_access_retries': 10,
    'fragment_retries': 10,
    'skip_unavailable_fragments': True,
    'keepvideo': False,
    'prefer_ffmpeg': True,
    'hls_prefer_native': False
}

class MusicControlView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="⏸️ Pause/Reprendre", style=discord.ButtonStyle.gray)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_data = get_channel_data(interaction.guild_id, self.channel_id)
        voice_client = guild_data['voice_clients'][self.channel_id]
        
        if voice_client:
            if voice_client.is_playing():
                voice_client.pause()
                await interaction.response.send_message("⏸️ Musique mise en pause", ephemeral=True)
            elif voice_client.is_paused():
                voice_client.resume()
                await interaction.response.send_message("▶️ Musique reprise", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Aucune musique en cours", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Bot non connecté", ephemeral=True)

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.gray)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_data = get_channel_data(interaction.guild_id, self.channel_id)
        voice_client = guild_data['voice_clients'][self.channel_id]
        
        if not voice_client:
            await interaction.response.send_message("❌ Bot non connecté", ephemeral=True)
            return

        if guild_data['queues'][self.channel_id]:
            voice_client.stop()
            await interaction.response.send_message("⏭️ Passage à la musique suivante...", ephemeral=True)
        else:
            voice_client.stop()
            guild_data['queues'][self.channel_id] = []
            await interaction.response.send_message("⏭️ Plus de musique dans la file.", ephemeral=True)

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_data = get_channel_data(interaction.guild_id, self.channel_id)
        voice_client = guild_data['voice_clients'][self.channel_id]
        
        if not voice_client:
            await interaction.response.send_message("❌ Bot non connecté", ephemeral=True)
            return

        voice_client.stop()
        guild_data['queues'][self.channel_id] = []
        guild_data['is_playing'][self.channel_id] = False
        
        if guild_data['controls_messages'][self.channel_id]:
            try:
                await guild_data['controls_messages'][self.channel_id].edit(embed=discord.Embed(
                    title="⏹️ Musique arrêtée",
                    description="La lecture a été arrêtée",
                    color=discord.Color.red()
                ), view=None)
            except discord.NotFound:
                pass
                
        await interaction.response.send_message("⏹️ Musique arrêtée", ephemeral=True)
