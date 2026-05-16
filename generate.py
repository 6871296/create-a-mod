#!/usr/bin/env python3
"""
CreateAMod Generator - reads createamod/config.createamod.json and generates block code + resources.
"""

import json
import os
import sys
import re
import glob
import zipfile

SOUND_TYPE_MAP = {
    "stone": "SoundType.STONE",
    "wood": "SoundType.WOOD",
    "grass": "SoundType.GRASS",
    "gravel": "SoundType.GRAVEL",
    "metal": "SoundType.METAL",
    "glass": "SoundType.GLASS",
    "wool": "SoundType.WOOL",
    "slime": "SoundType.SLIME_BLOCK",
    "snow": "SoundType.SNOW",
    "sand": "SoundType.SAND",
    "ladder": "SoundType.LADDER",
    "anvil": "SoundType.ANVIL",
    "bamboo": "SoundType.BAMBOO",
    "nether_wood": "SoundType.NETHER_WOOD",
    "netherite_block": "SoundType.NETHERITE_BLOCK",
    "copper": "SoundType.COPPER",
    "amethyst": "SoundType.AMETHYST",
}

MAP_COLOR_MAP = {
    "stone_gray": "MapColor.STONE",
    "dirt_brown": "MapColor.DIRT",
    "wood_brown": "MapColor.WOOD",
    "water_blue": "MapColor.WATER",
    "ice_blue": "MapColor.ICE",
    "red": "MapColor.COLOR_RED",
    "green": "MapColor.COLOR_GREEN",
    "blue": "MapColor.COLOR_BLUE",
    "yellow": "MapColor.COLOR_YELLOW",
    "white": "MapColor.COLOR_WHITE",
    "black": "MapColor.COLOR_BLACK",
    "orange": "MapColor.COLOR_ORANGE",
    "magenta": "MapColor.COLOR_MAGENTA",
    "light_blue": "MapColor.COLOR_LIGHT_BLUE",
    "lime": "MapColor.COLOR_LIME",
    "pink": "MapColor.COLOR_PINK",
    "gray": "MapColor.COLOR_GRAY",
    "light_gray": "MapColor.COLOR_LIGHT_GRAY",
    "cyan": "MapColor.COLOR_CYAN",
    "purple": "MapColor.COLOR_PURPLE",
    "brown": "MapColor.COLOR_BROWN",
    "sand": "MapColor.SAND",
    "snow": "MapColor.SNOW",
    "clay": "MapColor.CLAY",
    "nether": "MapColor.NETHER",
    "foliage": "MapColor.FOLIAGE",
}


def pascal_case(s):
    return ''.join(word.capitalize() for word in s.split('_'))


def const_case(s):
    return '_'.join(word.upper() for word in s.split('_'))


MAIN_CONFIG_PATH = 'createamod/config.createamod.json'


def load_main_config():
    if not os.path.exists(MAIN_CONFIG_PATH):
        print(f"Error: {MAIN_CONFIG_PATH} not found.")
        sys.exit(1)
    with open(MAIN_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_minecraft_block_registry(minecraft_version):
    """Extract existing block IDs from Minecraft client jar blockstates and common jar loot tables."""
    gradle_home = os.path.expanduser('~/.gradle')
    loom_dir = os.path.join(gradle_home, 'caches', 'fabric-loom', minecraft_version)

    client_jar = os.path.join(loom_dir, 'minecraft-client.jar')
    common_jar = os.path.join(loom_dir, 'minecraft-common.jar')

    blocks = set()

    def extract_from_jar(jar_path, prefix, suffix):
        if not os.path.exists(jar_path):
            return
        try:
            with zipfile.ZipFile(jar_path, 'r') as zf:
                for name in zf.namelist():
                    if name.startswith(prefix) and name.endswith(suffix):
                        # e.g. assets/minecraft/blockstates/grass_block.json -> grass_block
                        block_id = name[len(prefix):-len(suffix)]
                        if block_id:
                            blocks.add(block_id)
        except Exception as e:
            print(f"Warning: failed to read {jar_path}: {e}")

    # From client jar: assets/<namespace>/blockstates/*.json
    extract_from_jar(client_jar, 'assets/minecraft/blockstates/', '.json')
    # From common jar: data/<namespace>/loot_tables/blocks/*.json
    extract_from_jar(common_jar, 'data/minecraft/loot_tables/blocks/', '.json')

    return blocks


def is_item_config(config_data, file_path):
    """Determine if a config describes an item (not a block)."""
    path_parts = os.path.normpath(file_path).replace('\\', '/').split('/')
    if 'items' in path_parts:
        return True
    if 'blocks' in path_parts:
        return False

    textures = config_data.get('textures', {})
    if any(k.startswith('layer') for k in textures):
        return True
    if any(k.startswith('cube') for k in textures):
        return False

    item_keys = {'food', 'tool', 'armor', 'bow', 'crossbow', 'shield',
                 'potion', 'spawn_egg', 'music_disc', 'horse_armor',
                 'firework', 'enchanted_book'}
    if any(k in config_data for k in item_keys):
        return True

    return False


def load_blocks(main_config):
    """Load block and item configs based on the 'files' field in main config.
    Supports two formats:
      - Dict: {"blocks": "...", "items": "..."}
      - List: ["*.createamod.json"] (backward compatible, uses is_item_config)
    Returns (own_blocks, mixin_blocks, own_items).
    """
    own_modid = main_config.get('id', 'modid')
    mc_version = main_config.get('minecraft-version', '1.20.6')
    files_config = main_config.get('files', [])

    # Load known Minecraft blocks for validation
    known_mc_blocks = get_minecraft_block_registry(mc_version)
    if known_mc_blocks:
        print(f"Loaded {len(known_mc_blocks)} known Minecraft blocks for validation.")

    base_dir = 'createamod'
    block_files = set()
    item_files = set()

    if isinstance(files_config, dict):
        for key, pattern in files_config.items():
            search_path = os.path.join(base_dir, '**', pattern)
            matched = glob.glob(search_path, recursive=True)
            for fp in matched:
                fp = os.path.normpath(fp)
                if os.path.basename(fp).lower() == 'config.createamod.json':
                    continue
                if key == 'items':
                    item_files.add(fp)
                else:
                    block_files.add(fp)
    else:
        # Backward compatible: list of patterns
        for pattern in files_config:
            search_path = os.path.join(base_dir, '**', pattern)
            matched = glob.glob(search_path, recursive=True)
            for fp in matched:
                fp = os.path.normpath(fp)
                if os.path.basename(fp).lower() == 'config.createamod.json':
                    continue
                block_files.add(fp)

    own_blocks = []
    mixin_blocks = []
    own_items = []

    # Process block files
    for fp in sorted(block_files):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

            raw_id = cfg.get('id', '')
            if ':' in raw_id:
                namespace, block_id = raw_id.split(':', 1)
                cfg['namespace'] = namespace
                cfg['id'] = block_id
            else:
                namespace = own_modid
                cfg['namespace'] = own_modid
                block_id = raw_id

            if not isinstance(files_config, dict) and is_item_config(cfg, fp):
                if namespace == own_modid:
                    own_items.append(cfg)
                    print(f"Loaded own item: {fp} -> {block_id}")
                else:
                    print(f"Warning: item configs must use own modid, skipping {fp}")
                continue

            if namespace == own_modid:
                own_blocks.append(cfg)
                print(f"Loaded own block: {fp} -> {block_id}")
            else:
                if namespace == 'minecraft' and known_mc_blocks and block_id not in known_mc_blocks:
                    print(f"Ignored: {fp} -> {raw_id} does not exist in Minecraft {mc_version}.")
                    continue
                mixin_blocks.append(cfg)
                print(f"Loaded mixin block: {fp} -> {raw_id}")
        except Exception as e:
            print(f"Warning: failed to load {fp}: {e}")

    # Process item files
    for fp in sorted(item_files):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

            raw_id = cfg.get('id', '')
            if ':' in raw_id:
                namespace, item_id = raw_id.split(':', 1)
                cfg['namespace'] = namespace
                cfg['id'] = item_id
            else:
                namespace = own_modid
                cfg['namespace'] = own_modid
                item_id = raw_id

            if namespace == own_modid:
                own_items.append(cfg)
                print(f"Loaded own item: {fp} -> {item_id}")
            else:
                print(f"Warning: item configs must use own modid, skipping {fp}")
        except Exception as e:
            print(f"Warning: failed to load {fp}: {e}")

    return own_blocks, mixin_blocks, own_items


def generate_mod_blocks(config):
    modid = config['modid']
    group = config['group']
    blocks = config.get('own_blocks', [])

    if not blocks:
        print("No own blocks to generate.")
        return

    lines = [
        f'package {group}.block;',
        '',
        'import net.minecraft.core.Registry;',
        'import net.minecraft.core.registries.BuiltInRegistries;',
        'import net.minecraft.resources.ResourceLocation;',
        'import net.minecraft.world.level.block.Block;',
        'import net.minecraft.world.level.block.SoundType;',
        'import net.minecraft.world.level.block.state.BlockBehaviour;',
        'import net.minecraft.world.item.BlockItem;',
        'import net.minecraft.world.item.Item;',
        'import net.minecraft.world.level.material.MapColor;',
        '',
        f'public class ModBlocks {{',
        ''
    ]

    for block in blocks:
        block_id = block['id']
        field_name = const_case(block_id)
        lines.append(f'    public static Block {field_name};')

    lines.append('')
    lines.append('    public static void register() {')

    for block in blocks:
        block_id = block['id']
        field_name = const_case(block_id)
        settings_expr = build_settings_expr(block)
        lines.append(f'        {field_name} = registerBlock("{block_id}", {settings_expr});')

    lines.append('    }')
    lines.append('')
    lines.append('    private static Block registerBlock(String name, BlockBehaviour.Properties properties) {')
    lines.append('        Block block = new Block(properties);')
    lines.append(f'        ResourceLocation id = new ResourceLocation("{modid}", name);')
    lines.append('        Registry.register(BuiltInRegistries.BLOCK, id, block);')
    lines.append('        Registry.register(BuiltInRegistries.ITEM, id, new BlockItem(block, new Item.Properties()));')
    lines.append('        return block;')
    lines.append('    }')
    lines.append('')

    for block in blocks:
        block_id = block['id']
        method_name = 'createSettings_' + block_id.replace('-', '_').replace('.', '_')
        attrs = block.get('attributes', {})

        body_lines = []
        body_lines.append('        BlockBehaviour.Properties props = BlockBehaviour.Properties.of();')

        hardness = attrs.get('hardness', 0.0)
        resistance = attrs.get('resistance', 0.0)
        if hardness > 0 or resistance > 0:
            body_lines.append(f'        props = props.strength({hardness}f, {resistance}f);')

        luminance = attrs.get('luminance', 0)
        if luminance > 0:
            body_lines.append(f'        props = props.lightLevel(state -> {luminance});')

        sounds = attrs.get('sounds', '')
        if sounds and sounds.lower() in SOUND_TYPE_MAP:
            body_lines.append(f'        props = props.sound({SOUND_TYPE_MAP[sounds.lower()]});')

        map_color = attrs.get('map_color', '')
        if map_color and map_color.lower() in MAP_COLOR_MAP:
            body_lines.append(f'        props = props.mapColor({MAP_COLOR_MAP[map_color.lower()]});')

        slipperiness = attrs.get('slipperiness', 0.6)
        if slipperiness != 0.6:
            body_lines.append(f'        props = props.friction({slipperiness}f);')

        if attrs.get('requires_tool', False):
            body_lines.append('        props = props.requiresCorrectToolForDrops();')
        if attrs.get('break_instantly', False):
            body_lines.append('        props = props.instabreak();')
        if attrs.get('non_opaque', False):
            body_lines.append('        props = props.noOcclusion();')
        if attrs.get('no_collision', False):
            body_lines.append('        props = props.noCollission();')
        if attrs.get('burnable', False):
            body_lines.append('        props = props.ignitedByLava();')
        if attrs.get('replaceable', False):
            body_lines.append('        props = props.replaceable();')
        if attrs.get('ticks_randomly', False):
            body_lines.append('        props = props.randomTicks();')
        if attrs.get('air', False):
            body_lines.append('        props = props.air();')

        body_lines.append('        return props;')

        lines.append(f'    private static BlockBehaviour.Properties {method_name}() {{')
        lines.extend(body_lines)
        lines.append('    }')
        lines.append('')

    lines.append('}')

    pkg_path = group.replace('.', '/')
    output_dir = f'src/main/java/{pkg_path}/block'
    os.makedirs(output_dir, exist_ok=True)
    output_path = f'{output_dir}/ModBlocks.java'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Generated: {output_path}")


def build_settings_expr(block):
    block_id = block['id']
    method_name = 'createSettings_' + block_id.replace('-', '_').replace('.', '_')
    return f'{method_name}()'


def build_item_props_expr(item):
    item_id = item['id']
    method_name = 'createProperties_' + item_id.replace('-', '_').replace('.', '_')
    return f'{method_name}()'


def generate_mod_items(config):
    modid = config['modid']
    group = config['group']
    items = config.get('own_items', [])

    if not items:
        print("No own items to generate.")
        return

    lines = [
        f'package {group}.item;',
        '',
        'import net.minecraft.core.Registry;',
        'import net.minecraft.core.registries.BuiltInRegistries;',
        'import net.minecraft.resources.ResourceLocation;',
        'import net.minecraft.world.effect.MobEffectInstance;',
        'import net.minecraft.world.food.FoodProperties;',
        'import net.minecraft.world.item.Item;',
        'import net.minecraft.world.item.Rarity;',
        '',
        f'public class ModItems {{',
        ''
    ]

    for item in items:
        item_id = item['id']
        field_name = const_case(item_id)
        lines.append(f'    public static Item {field_name};')

    lines.append('')
    lines.append('    public static void register() {')

    for item in items:
        item_id = item['id']
        field_name = const_case(item_id)
        props_expr = build_item_props_expr(item)
        lines.append(f'        {field_name} = registerItem("{item_id}", {props_expr});')

    lines.append('    }')
    lines.append('')
    lines.append('    private static Item registerItem(String name, Item.Properties properties) {')
    lines.append('        Item item = new Item(properties);')
    lines.append(f'        ResourceLocation id = new ResourceLocation("{modid}", name);')
    lines.append('        Registry.register(BuiltInRegistries.ITEM, id, item);')
    lines.append('        return item;')
    lines.append('    }')
    lines.append('')

    for item in items:
        item_id = item['id']
        method_name = 'createProperties_' + item_id.replace('-', '_').replace('.', '_')
        attrs = item.get('attributes', {})

        body_lines = []
        body_lines.append('        Item.Properties props = new Item.Properties();')

        max_stack = attrs.get('max_stack', 64)
        if max_stack != 64:
            body_lines.append(f'        props = props.stacksTo({max_stack});')

        durability = attrs.get('durability', 0)
        if durability > 0:
            body_lines.append(f'        props = props.durability({durability});')

        if attrs.get('fire_resistant', False):
            body_lines.append('        props = props.fireResistant();')

        rarity = attrs.get('rarity', 'common')
        if rarity and rarity.lower() != 'common':
            body_lines.append(f'        props = props.rarity(Rarity.{rarity.upper()});')

        food = item.get('food')
        if food:
            body_lines.append('        FoodProperties.Builder foodBuilder = new FoodProperties.Builder();')
            nutrition = food.get('nutrition', 0)
            if nutrition > 0:
                body_lines.append(f'        foodBuilder = foodBuilder.nutrition({nutrition});')
            saturation = food.get('saturation', 0)
            if saturation > 0:
                body_lines.append(f'        foodBuilder = foodBuilder.saturationModifier({saturation}f);')
            if food.get('always_edible', False):
                body_lines.append('        foodBuilder = foodBuilder.alwaysEdible();')
            if food.get('fast_eating', False):
                body_lines.append('        foodBuilder = foodBuilder.fast();')
            effects = food.get('effects', [])
            for effect in effects:
                effect_id = effect.get('effect', '')
                duration = effect.get('duration', 100)
                amplifier = effect.get('amplifier', 0)
                probability = effect.get('probability', 1.0)
                if ':' not in effect_id:
                    effect_id = f'minecraft:{effect_id}'
                ns, eff_name = effect_id.split(':', 1)
                body_lines.append('        foodBuilder = foodBuilder.effect(')
                body_lines.append('            new MobEffectInstance(')
                body_lines.append(f'                BuiltInRegistries.MOB_EFFECT.getHolder(new ResourceLocation("{ns}", "{eff_name}")).orElseThrow(),')
                body_lines.append(f'                {duration}, {amplifier}')
                body_lines.append('            ),')
                body_lines.append(f'            {probability}f')
                body_lines.append('        );')
            body_lines.append('        props = props.food(foodBuilder.build());')

        enchantment_value = attrs.get('enchantment_value', 0)
        if enchantment_value > 0:
            body_lines.append(f'        // TODO: enchantment_value ({enchantment_value}) requires DataComponent setup in 1.20.6')

        body_lines.append('        return props;')

        lines.append(f'    private static Item.Properties {method_name}() {{')
        lines.extend(body_lines)
        lines.append('    }')
        lines.append('')

    lines.append('}')

    pkg_path = group.replace('.', '/')
    output_dir = f'src/main/java/{pkg_path}/item'
    os.makedirs(output_dir, exist_ok=True)
    output_path = f'{output_dir}/ModItems.java'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Generated: {output_path}")


def update_example_mod(config):
    group = config['group']
    mod_file = f'src/main/java/{group.replace(".", "/")}/ExampleMod.java'

    if not os.path.exists(mod_file):
        print(f"Warning: {mod_file} not found, skipping ExampleMod update.")
        return

    with open(mod_file, 'r', encoding='utf-8') as f:
        content = f.read()

    import_line = f'import {group}.block.ModBlocks;'
    if import_line not in content:
        if 'import ' in content:
            content = content.replace('import ', f'{import_line}\nimport ', 1)
        else:
            content = content.replace('package ', f'{import_line}\n\npackage ', 1)

    import_line_items = f'import {group}.item.ModItems;'
    if import_line_items not in content:
        if 'import ' in content:
            content = content.replace('import ', f'{import_line_items}\nimport ', 1)
        else:
            content = content.replace('package ', f'{import_line_items}\n\npackage ', 1)

    register_call = 'ModBlocks.register();'
    if register_call not in content:
        if 'LOGGER.info' in content:
            lines = content.split('\n')
            new_lines = []
            inserted = False
            for i, line in enumerate(lines):
                new_lines.append(line)
                if not inserted and 'LOGGER.info' in line and i + 1 < len(lines):
                    indent = '        '
                    new_lines.append(f'{indent}{register_call}')
                    inserted = True
            content = '\n'.join(new_lines)
        else:
            content = content.rstrip()
            if content.endswith('}'):
                content = content[:-1] + f'        {register_call}\n    }}\n}}'

    register_call_items = 'ModItems.register();'
    if register_call_items not in content:
        if 'LOGGER.info' in content:
            lines = content.split('\n')
            new_lines = []
            inserted = False
            for i, line in enumerate(lines):
                new_lines.append(line)
                if not inserted and 'LOGGER.info' in line and i + 1 < len(lines):
                    indent = '        '
                    new_lines.append(f'{indent}{register_call_items}')
                    inserted = True
            content = '\n'.join(new_lines)
        else:
            content = content.rstrip()
            if content.endswith('}'):
                content = content[:-1] + f'        {register_call_items}\n    }}\n}}'

    with open(mod_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Updated: {mod_file}")


def generate_blockstates(config):
    own_blocks = config.get('own_blocks', [])
    mixin_blocks = config.get('mixin_blocks', [])

    for block in own_blocks + mixin_blocks:
        block_id = block['id']
        namespace = block.get('namespace', config['modid'])

        # Skip mixin blocks without custom textures (preserve original blockstates)
        if block in mixin_blocks and not block.get('textures'):
            continue

        data = {
            "variants": {
                "": {
                    "model": f"{namespace}:block/{block_id}"
                }
            }
        }
        output_dir = f'src/main/resources/assets/{namespace}/blockstates'
        os.makedirs(output_dir, exist_ok=True)
        path = f'{output_dir}/{block_id}.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Generated: {path}")


def generate_models(config):
    own_blocks = config.get('own_blocks', [])
    mixin_blocks = config.get('mixin_blocks', [])

    for block in own_blocks + mixin_blocks:
        block_id = block['id']
        namespace = block.get('namespace', config['modid'])
        textures = block.get('textures', {})

        # Skip mixin blocks without custom textures (preserve original models)
        if block in mixin_blocks and not textures:
            continue

        if 'cube_all' in textures:
            block_model = {
                "parent": "minecraft:block/cube_all",
                "textures": {
                    "all": textures['cube_all'].replace('assets/', '').replace('/textures', '').replace('/block/', ':block/')
                }
            }
        else:
            texture_map = {}
            face_map = {
                'cube_x+': 'east',
                'cube_x-': 'west',
                'cube_z+': 'south',
                'cube_z-': 'north',
                'cube_y+': 'up',
                'cube_y-': 'down',
            }
            for key, face in face_map.items():
                if key in textures:
                    val = textures[key]
                    val = val.replace('assets/', '').replace('/textures', '').replace('/block/', ':block/')
                    texture_map[face] = val

            if texture_map:
                block_model = {
                    "parent": "minecraft:block/cube",
                    "textures": texture_map
                }
            else:
                block_model = {
                    "parent": "minecraft:block/cube_all",
                    "textures": {
                        "all": f"{namespace}:block/{block_id}"
                    }
                }

        block_models_dir = f'src/main/resources/assets/{namespace}/models/block'
        os.makedirs(block_models_dir, exist_ok=True)
        path = f'{block_models_dir}/{block_id}.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(block_model, f, indent=4, ensure_ascii=False)
        print(f"Generated: {path}")

        # Item model for own blocks only (mixin blocks already exist in original mod)
        if block in own_blocks:
            item_models_dir = f'src/main/resources/assets/{namespace}/models/item'
            os.makedirs(item_models_dir, exist_ok=True)
            item_model = {
                "parent": f"{namespace}:block/{block_id}"
            }
            path = f'{item_models_dir}/{block_id}.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(item_model, f, indent=4, ensure_ascii=False)
            print(f"Generated: {path}")

    # Item models
    own_items = config.get('own_items', [])
    for item in own_items:
        item_id = item['id']
        namespace = item.get('namespace', config['modid'])
        textures = item.get('textures', {})

        item_models_dir = f'src/main/resources/assets/{namespace}/models/item'
        os.makedirs(item_models_dir, exist_ok=True)

        texture_map = {}
        for layer_key in ['layer0', 'layer1']:
            if layer_key in textures:
                val = textures[layer_key]
                val = val.replace('assets/', '').replace('/textures', '').replace('/item/', ':item/')
                texture_map[layer_key] = val

        if not texture_map:
            texture_map['layer0'] = f'{namespace}:item/{item_id}'

        item_model = {
            "parent": "minecraft:item/generated",
            "textures": texture_map
        }
        path = f'{item_models_dir}/{item_id}.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(item_model, f, indent=4, ensure_ascii=False)
        print(f"Generated: {path}")


def generate_lang(config):
    own_blocks = config.get('own_blocks', [])
    mixin_blocks = config.get('mixin_blocks', [])

    lang_data = {}

    for block in own_blocks + mixin_blocks:
        block_id = block['id']
        namespace = block.get('namespace', config['modid'])
        names = block.get('name', {})
        key = f'block.{namespace}.{block_id}'
        for lang_code, value in names.items():
            if lang_code not in lang_data:
                lang_data[lang_code] = {}
            lang_data[lang_code][key] = value

    own_items = config.get('own_items', [])
    for item in own_items:
        item_id = item['id']
        namespace = item.get('namespace', config['modid'])
        names = item.get('name', {})
        key = f'item.{namespace}.{item_id}'
        for lang_code, value in names.items():
            if lang_code not in lang_data:
                lang_data[lang_code] = {}
            lang_data[lang_code][key] = value

    for lang_code, entries in lang_data.items():
        # For mixin blocks targeting minecraft namespace, place lang in our mod's assets
        # so Minecraft can override via resource pack priority
        output_namespace = config['modid']
        lang_dir = f'src/main/resources/assets/{output_namespace}/lang'
        os.makedirs(lang_dir, exist_ok=True)
        path = f'{lang_dir}/{lang_code}.json'

        # Merge with existing file if present
        existing = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing.update(entries)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)
        print(f"Generated: {path}")


def generate_mixins(config):
    """Generate Mixin classes for mixin blocks to modify attributes of existing blocks.
    Supports: luminance, sounds, requires_tool, non_opaque, no_collision, burnable, air, ticks_randomly, instrument
    """
    group = config['group']
    mixin_blocks = config.get('mixin_blocks', [])

    if not mixin_blocks:
        return

    pkg_path = group.replace('.', '/')
    mixin_dir = f'src/main/java/{pkg_path}/mixin'
    os.makedirs(mixin_dir, exist_ok=True)

    # (attribute_key, method_name, return_type, value_transform, invert_bool)
    METHOD_MAP = [
        ('luminance', 'getLightEmission', 'Integer', lambda v: str(v), False),
        ('sounds', 'getSoundType', 'SoundType', lambda v: SOUND_TYPE_MAP.get(v.lower(), 'SoundType.STONE'), False),
        ('requires_tool', 'requiresCorrectToolForDrops', 'Boolean', lambda v: 'true' if v else 'false', False),
        ('non_opaque', 'canOcclude', 'Boolean', lambda v: 'false' if v else 'true', True),
        ('no_collision', 'blocksMotion', 'Boolean', lambda v: 'false' if v else 'true', True),
        ('burnable', 'ignitedByLava', 'Boolean', lambda v: 'true' if v else 'false', False),
        ('air', 'isAir', 'Boolean', lambda v: 'true' if v else 'false', False),
        ('ticks_randomly', 'isRandomlyTicking', 'Boolean', lambda v: 'true' if v else 'false', False),
        ('instrument', 'instrument', 'NoteBlockInstrument', lambda v: f'NoteBlockInstrument.{v.upper()}', False),
    ]

    # Collect modifications per block
    block_modifications = []
    for block in mixin_blocks:
        attrs = block.get('attributes', {})
        mods = []
        for attr_key, method_name, return_type, transform, invert in METHOD_MAP:
            if attr_key not in attrs:
                continue
            value = attrs[attr_key]
            # Skip defaults
            if attr_key == 'luminance' and value == 0:
                continue
            if attr_key == 'sounds' and (not value or value.lower() == 'stone'):
                continue
            if attr_key == 'instrument' and (not value or value.lower() == 'harp'):
                continue
            if isinstance(value, bool) and not value:
                continue
            if isinstance(value, float) and value == 0.6:
                continue
            java_value = transform(value)
            mods.append((method_name, return_type, java_value))
        if mods:
            block_modifications.append((block, mods))

    if block_modifications:
        class_name = 'BlockMixin'
        # Check which imports are actually needed
        needs_sound_type = any(m[0] == 'getSoundType' for _, mods in block_modifications for m in mods)
        needs_instrument = any(m[0] == 'instrument' for _, mods in block_modifications for m in mods)

        lines = [
            f'package {group}.mixin;',
            '',
            'import net.minecraft.core.registries.BuiltInRegistries;',
            'import net.minecraft.resources.ResourceLocation;',
            'import net.minecraft.world.level.block.Block;',
        ]
        if needs_sound_type:
            lines.append('import net.minecraft.world.level.block.SoundType;')
        if needs_instrument:
            lines.append('import net.minecraft.world.level.block.state.properties.NoteBlockInstrument;')
        lines.extend([
            'import net.minecraft.world.level.block.state.BlockBehaviour;',
            'import org.spongepowered.asm.mixin.Mixin;',
            'import org.spongepowered.asm.mixin.Shadow;',
            'import org.spongepowered.asm.mixin.injection.At;',
            'import org.spongepowered.asm.mixin.injection.Inject;',
            'import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;',
            '',
            '@Mixin(BlockBehaviour.BlockStateBase.class)',
            f'public abstract class {class_name} {{',
            '',
            '    @Shadow',
            '    public abstract boolean is(Block block);',
            ''
        ])

        generated_methods = set()
        for block, mods in block_modifications:
            block_id = block['id']
            namespace = block.get('namespace', 'minecraft')
            block_key = f'{namespace}:{block_id}'

            for method_name, return_type, java_value in mods:
                method_key = f'{method_name}_{block_key}'
                if method_key in generated_methods:
                    continue
                generated_methods.add(method_key)

                # Use a single injected method per target block per attribute method
                inject_method_name = f'on{method_name[0].upper()}{method_name[1:]}_{namespace}_{block_id}'.replace('-', '_').replace('.', '_')
                cir_type = f'CallbackInfoReturnable<{return_type}>'

                lines.append(f'    @Inject(method = "{method_name}", at = @At("HEAD"), cancellable = true)')
                lines.append(f'    private void {inject_method_name}({cir_type} cir) {{')
                lines.append(f'        if (this.is(BuiltInRegistries.BLOCK.get(new ResourceLocation("{namespace}", "{block_id}")))) {{')
                lines.append(f'            cir.setReturnValue({java_value});')
                lines.append('            return;')
                lines.append('        }')
                lines.append('    }')
                lines.append('')

        lines.append('}')

        path = f'{mixin_dir}/{class_name}.java'
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"Generated: {path}")

    # Clean up old BlockLightMixin if exists
    old_mixin = f'{mixin_dir}/BlockLightMixin.java'
    if os.path.exists(old_mixin):
        os.remove(old_mixin)
        print(f"Removed old: {old_mixin}")

    # Register mixins in modid.mixins.json
    mixins_json = f'src/main/resources/{config["modid"]}.mixins.json'
    if os.path.exists(mixins_json):
        with open(mixins_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

        mixin_entries = data.get('mixins', [])
        # Remove old BlockLightMixin
        if 'BlockLightMixin' in mixin_entries:
            mixin_entries.remove('BlockLightMixin')
        # Add BlockMixin
        if 'BlockMixin' not in mixin_entries and f'{group}.mixin.BlockMixin' not in mixin_entries:
            mixin_entries.append('BlockMixin')
        data['mixins'] = mixin_entries
        with open(mixins_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Updated: {mixins_json}")

    # Print hints for unsupported attributes
    print("\n[Mixin Blocks - Auto & Manual Attributes]")
    auto_attrs = {m[0] for m in METHOD_MAP}
    for block in mixin_blocks:
        block_id = block['id']
        namespace = block.get('namespace', 'minecraft')
        attrs = block.get('attributes', {})
        unsupported = []
        for key, value in attrs.items():
            if key in auto_attrs:
                continue
            if value and value != 0 and value != 0.6 and value != False:
                unsupported.append(f"{key} = {value}")
        if unsupported:
            print(f"  - {namespace}:{block_id} needs manual Mixin for:")
            for item in unsupported:
                print(f"      {item}")
        drops = block.get('drops', [])
        if drops:
            print(f"  - {namespace}:{block_id} has custom drops that need Loot Table modification.")
    print("[End Mixin Hints]\n")


def clean_generated_resources(config):
    """Clean old generated resources under the mod's namespace to avoid stale files."""
    modid = config['modid']
    dirs = [
        f'src/main/resources/assets/{modid}/blockstates',
        f'src/main/resources/assets/{modid}/models/block',
        f'src/main/resources/assets/{modid}/models/item',
    ]
    for d in dirs:
        if os.path.exists(d):
            import shutil
            shutil.rmtree(d)
            print(f"Cleaned: {d}")


def copy_textures(config):
    """Copy texture images from createamod/images/ to the resource directory.
    Matches image filenames against block/item IDs, normalizing underscores and hyphens.
    """
    import shutil
    modid = config['modid']
    images_dir = 'createamod/images'

    if not os.path.isdir(images_dir):
        return

    # Build a case-insensitive lookup with both _ and - variants
    available = {}
    for fname in os.listdir(images_dir):
        if fname.lower().endswith('.png'):
            base = fname[:-4]
            path = os.path.join(images_dir, fname)
            for variant in {base.lower(), base.lower().replace('_', '-'), base.lower().replace('-', '_')}:
                available[variant] = path

    def find_image(candidates):
        for name in candidates:
            key = name.lower()
            if key in available:
                return available[key]
        return None

    def should_copy(src, dst):
        return not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)

    # Block textures
    for block in config.get('own_blocks', []):
        block_id = block['id']
        textures = block.get('textures', {})
        target_dir = f'src/main/resources/assets/{modid}/textures/block'

        if 'cube_all' in textures:
            target_path = os.path.join(target_dir, f'{block_id}.png')
            img = find_image([block_id, f'{block_id}-all', f'{block_id}_all'])
            if img and should_copy(img, target_path):
                os.makedirs(target_dir, exist_ok=True)
                shutil.copy2(img, target_path)
                print(f"Copied texture: {img} -> {target_path}")

        face_map = {
            'cube_x+': 'east', 'cube_x-': 'west',
            'cube_z+': 'south', 'cube_z-': 'north',
            'cube_y+': 'up', 'cube_y-': 'down',
        }
        for key, face in face_map.items():
            if key in textures:
                target_path = os.path.join(target_dir, f'{block_id}.png')
                img = find_image([block_id, f'{block_id}-{face}', f'{block_id}_{face}'])
                if img and should_copy(img, target_path):
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.copy2(img, target_path)
                    print(f"Copied texture: {img} -> {target_path}")

    # Item textures
    for item in config.get('own_items', []):
        item_id = item['id']
        textures = item.get('textures', {})
        target_dir = f'src/main/resources/assets/{modid}/textures/item'

        for layer_key in ['layer0', 'layer1']:
            if layer_key in textures:
                target_path = os.path.join(target_dir, f'{item_id}.png')
                img = find_image([item_id])
                if img and should_copy(img, target_path):
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.copy2(img, target_path)
                    print(f"Copied texture: {img} -> {target_path}")


def sync_modid(config, main_config):
    """Sync modid, name, description, author from main config to project files."""
    modid = config['modid']
    old_modid = None

    fabric_mod_json = 'src/main/resources/fabric.mod.json'
    if os.path.exists(fabric_mod_json):
        with open(fabric_mod_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        old_modid = data.get('id', 'modid')
    else:
        return

    if old_modid == modid:
        # Still sync name/description/author even if modid unchanged
        pass
    else:
        print(f"Syncing modid from '{old_modid}' to '{modid}'...")

        # 1. Update fabric.mod.json
        with open(fabric_mod_json, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace(f'"id": "{old_modid}"', f'"id": "{modid}"')
        content = content.replace(f'"icon": "assets/{old_modid}/icon.png"', f'"icon": "assets/{modid}/icon.png"')
        content = content.replace(f'"{old_modid}.mixins.json"', f'"{modid}.mixins.json"')
        content = content.replace(f'"{old_modid}.client.mixins.json"', f'"{modid}.client.mixins.json"')
        with open(fabric_mod_json, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {fabric_mod_json}")

        # 2. Update ExampleMod.java MOD_ID
        example_mod = f"src/main/java/{config['group'].replace('.', '/')}/ExampleMod.java"
        if os.path.exists(example_mod):
            with open(example_mod, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace(f'MOD_ID = "{old_modid}"', f'MOD_ID = "{modid}"')
            with open(example_mod, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {example_mod}")

        # 3. Migrate assets directory: copy icon, move lang, delete the rest
        old_assets = f'src/main/resources/assets/{old_modid}'
        new_assets = f'src/main/resources/assets/{modid}'
        if os.path.exists(old_assets):
            os.makedirs(new_assets, exist_ok=True)
            # Copy icon.png if exists
            old_icon = os.path.join(old_assets, 'icon.png')
            new_icon = os.path.join(new_assets, 'icon.png')
            if os.path.exists(old_icon):
                import shutil
                shutil.copy2(old_icon, new_icon)
                print(f"Copied: {old_icon} -> {new_icon}")
            # Move lang directory if exists
            old_lang = os.path.join(old_assets, 'lang')
            new_lang = os.path.join(new_assets, 'lang')
            if os.path.exists(old_lang) and not os.path.exists(new_lang):
                os.rename(old_lang, new_lang)
                print(f"Moved: {old_lang} -> {new_lang}")
            # Remove old assets dir (blockstates/models will be regenerated)
            import shutil
            shutil.rmtree(old_assets)
            print(f"Removed old assets: {old_assets}")

        # 4. Rename main mixins.json
        old_mixins = f'src/main/resources/{old_modid}.mixins.json'
        new_mixins = f'src/main/resources/{modid}.mixins.json'
        if os.path.exists(old_mixins) and not os.path.exists(new_mixins):
            os.rename(old_mixins, new_mixins)
            print(f"Renamed: {old_mixins} -> {new_mixins}")

        # 5. Rename client mixins.json
        old_client_mixins = f'src/client/resources/{old_modid}.client.mixins.json'
        new_client_mixins = f'src/client/resources/{modid}.client.mixins.json'
        if os.path.exists(old_client_mixins) and not os.path.exists(new_client_mixins):
            os.rename(old_client_mixins, new_client_mixins)
            print(f"Renamed: {old_client_mixins} -> {new_client_mixins}")

        # 6. Update settings.gradle
        settings = 'settings.gradle'
        if os.path.exists(settings):
            with open(settings, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace(f"rootProject.name = '{old_modid}'", f"rootProject.name = '{modid}'")
            with open(settings, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {settings}")

        # 7. Update build.gradle loom.mods block
        build_gradle = 'build.gradle'
        if os.path.exists(build_gradle):
            with open(build_gradle, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace(f'"{old_modid}" {{', f'"{modid}" {{')
            with open(build_gradle, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {build_gradle}")

    # Sync gradle.properties (minecraft_version, mod_version, maven_group)
    gradle_props = 'gradle.properties'
    if os.path.exists(gradle_props):
        with open(gradle_props, 'r', encoding='utf-8') as f:
            content = f.read()
        prop_changed = False
        mc_ver = main_config.get('minecraft-version', '')
        if mc_ver and f'minecraft_version={mc_ver}' not in content:
            content = re.sub(r'minecraft_version=.+', f'minecraft_version={mc_ver}', content)
            prop_changed = True
        mod_ver = main_config.get('version', '')
        if mod_ver and f'mod_version={mod_ver}' not in content:
            content = re.sub(r'mod_version=.+', f'mod_version={mod_ver}', content)
            prop_changed = True
        group = main_config.get('group', '')
        if group and f'maven_group={group}' not in content:
            content = re.sub(r'maven_group=.+', f'maven_group={group}', content)
            prop_changed = True
        if prop_changed:
            with open(gradle_props, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated: {gradle_props}")

    # Always sync name, description, author
    with open(fabric_mod_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    changed = False
    if 'name' in main_config and data.get('name') != main_config['name']:
        data['name'] = main_config['name']
        changed = True
    if 'description' in main_config and data.get('description') != main_config['description']:
        data['description'] = main_config['description']
        changed = True
    if 'author' in main_config:
        authors = [main_config['author']] if main_config['author'] else []
        if data.get('authors') != authors:
            data['authors'] = authors
            changed = True

    if changed:
        with open(fabric_mod_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Updated: {fabric_mod_json} (name/description/author)")


def sync_group(config):
    """Sync Java package group by moving files and updating package declarations."""
    new_group = config['group']
    old_group = None

    # Find old group from ExampleMod.java
    example_mod_path = None
    for root, dirs, files in os.walk('src/main/java'):
        if 'ExampleMod.java' in files:
            example_mod_path = os.path.join(root, 'ExampleMod.java')
            break

    if example_mod_path:
        with open(example_mod_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('package '):
                    old_group = line[len('package '):].strip().rstrip(';')
                    break

    if not old_group or old_group == new_group:
        return

    print(f"Syncing group from '{old_group}' to '{new_group}'...")

    # Update all Java files
    java_files = []
    for src_dir in ['src/main/java', 'src/client/java']:
        if not os.path.exists(src_dir):
            continue
        for root, dirs, files in os.walk(src_dir):
            for fname in files:
                if fname.endswith('.java'):
                    java_files.append(os.path.join(root, fname))

    old_pkg_path = old_group.replace('.', '/')
    new_pkg_path = new_group.replace('.', '/')

    for old_path in java_files:
        with open(old_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Only process files that reference the old group
        if old_group not in content:
            continue

        # Replace package and imports
        content = content.replace(f'package {old_group}', f'package {new_group}')
        content = content.replace(f'import {old_group}', f'import {new_group}')

        # Compute new path
        rel_path = os.path.relpath(old_path, 'src')
        new_rel_path = rel_path.replace(old_pkg_path, new_pkg_path)
        new_path = os.path.join('src', new_rel_path)

        # Ensure directory exists
        os.makedirs(os.path.dirname(new_path), exist_ok=True)

        # Write new file
        with open(new_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Remove old file
        os.remove(old_path)
        print(f"Moved: {old_path} -> {new_path}")

    # Clean up empty directories
    for src_dir in ['src/main/java', 'src/client/java']:
        if not os.path.exists(src_dir):
            continue
        for root, dirs, files in os.walk(src_dir, topdown=False):
            if root == src_dir:
                continue
            try:
                if not os.listdir(root):
                    os.rmdir(root)
                    print(f"Removed empty dir: {root}")
            except OSError:
                pass

    # Update fabric.mod.json entrypoints
    fabric_mod_json = 'src/main/resources/fabric.mod.json'
    if os.path.exists(fabric_mod_json):
        with open(fabric_mod_json, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace(old_group, new_group)
        with open(fabric_mod_json, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {fabric_mod_json}")

    # Update mixins JSON packages
    modid = config['modid']
    mixins_json = f'src/main/resources/{modid}.mixins.json'
    if os.path.exists(mixins_json):
        with open(mixins_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('package', '').startswith(old_group):
            data['package'] = data['package'].replace(old_group, new_group)
            with open(mixins_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"Updated: {mixins_json}")

    client_mixins_json = f'src/client/resources/{modid}.client.mixins.json'
    if os.path.exists(client_mixins_json):
        with open(client_mixins_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('package', '').startswith(old_group):
            data['package'] = data['package'].replace(old_group, new_group)
            with open(client_mixins_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"Updated: {client_mixins_json}")


def main():
    main_config = load_main_config()
    own_blocks, mixin_blocks, own_items = load_blocks(main_config)
    config = {
        'modid': main_config.get('id', 'modid'),
        'group': main_config.get('group', 'com.example'),
        'own_blocks': own_blocks,
        'mixin_blocks': mixin_blocks,
        'own_items': own_items,
    }
    sync_modid(config, main_config)
    sync_group(config)
    clean_generated_resources(config)
    copy_textures(config)
    generate_mod_blocks(config)
    generate_mod_items(config)
    update_example_mod(config)
    generate_blockstates(config)
    generate_models(config)
    generate_lang(config)
    generate_mixins(config)
    print("\nUpdate complete!")


if __name__ == '__main__':
    main()
