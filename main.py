
import os
import discord
from discord.ext import commands
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Spotify setup
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv('SPOTIFY_CLIENT_ID'),
    client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
))

# Make Spotify client available to cogs
bot.sp = sp

@bot.event
async def on_ready():
    # Load music cog
    await bot.load_extension("src.cogs.music")
    await bot.tree.sync()

    print(f'\n=== Informations du Bot ===')
    print(f'Nom du bot: {bot.user.name}')
    print(f'ID du bot: {bot.user.id}')
    print(f'Version Discord.py: {discord.__version__}')
    print(f'\n=== Serveurs connectés ===')
    for guild in bot.guilds:
        try:
            invite = await guild.text_channels[0].create_invite(max_age=300)
            print(f'• {guild.name} (ID: {guild.id}) - Lien: {invite.url}')
        except:
            print(f'• {guild.name} (ID: {guild.id}) - Impossible de créer une invitation')
    print(f'\nBot prêt et connecté à {len(bot.guilds)} serveurs!')

bot.run(os.getenv("DISCORD_TOKEN"))
