def cdragon_asset_url(path: str) -> str:
    return "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default" + path

tile = "/lol-game-data/assets/ASSETS/Characters/Garen/Skins/Skin13/Images/garen_splash_tile_13.jpg"
print(cdragon_asset_url(tile))