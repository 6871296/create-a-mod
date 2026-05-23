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
import hashlib

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
    entity_files = set()

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
                elif key == 'entities':
                    entity_files.add(fp)
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
                path_parts = fp.replace('\\', '/').split('/')
                if 'entities' in path_parts:
                    entity_files.add(fp)
                elif 'items' in path_parts:
                    item_files.add(fp)
                else:
                    block_files.add(fp)

    own_blocks = []
    mixin_blocks = []
    own_items = []
    mixin_items = []
    own_entities = []
    mixin_entities = []

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

            if not isinstance(files_config, dict):
                path_parts = fp.replace('\\', '/').split('/')
                if 'entities' in path_parts:
                    if namespace == own_modid:
                        own_entities.append(cfg)
                        print(f"Loaded own entity: {fp} -> {block_id}")
                    else:
                        mixin_entities.append(cfg)
                        print(f"Loaded mixin entity: {fp} -> {raw_id}")
                    continue
                if is_item_config(cfg, fp):
                    if namespace == own_modid:
                        own_items.append(cfg)
                        print(f"Loaded own item: {fp} -> {block_id}")
                    else:
                        mixin_items.append(cfg)
                        print(f"Loaded mixin item: {fp} -> {raw_id}")
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
                mixin_items.append(cfg)
                print(f"Loaded mixin item: {fp} -> {raw_id}")
        except Exception as e:
            print(f"Warning: failed to load {fp}: {e}")

    # Process entity files
    for fp in sorted(entity_files):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

            raw_id = cfg.get('id', '')
            if ':' in raw_id:
                namespace, entity_id = raw_id.split(':', 1)
                cfg['namespace'] = namespace
                cfg['id'] = entity_id
            else:
                namespace = own_modid
                cfg['namespace'] = own_modid
                entity_id = raw_id

            if namespace == own_modid:
                own_entities.append(cfg)
                print(f"Loaded own entity: {fp} -> {entity_id}")
            else:
                mixin_entities.append(cfg)
                print(f"Loaded mixin entity: {fp} -> {raw_id}")
        except Exception as e:
            print(f"Warning: failed to load {fp}: {e}")

    return own_blocks, mixin_blocks, own_items, mixin_items, own_entities, mixin_entities


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

    import_line_entities = f'import {group}.entity.ModEntities;'
    if import_line_entities not in content:
        if 'import ' in content:
            content = content.replace('import ', f'{import_line_entities}\nimport ', 1)
        else:
            content = content.replace('package ', f'{import_line_entities}\n\npackage ', 1)

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

    register_call_entities = 'ModEntities.register();'
    if register_call_entities not in content:
        if 'LOGGER.info' in content:
            lines = content.split('\n')
            new_lines = []
            inserted = False
            for i, line in enumerate(lines):
                new_lines.append(line)
                if not inserted and 'LOGGER.info' in line and i + 1 < len(lines):
                    indent = '        '
                    new_lines.append(f'{indent}{register_call_entities}')
                    inserted = True
            content = '\n'.join(new_lines)
        else:
            content = content.rstrip()
            if content.endswith('}'):
                content = content[:-1] + f'        {register_call_entities}\n    }}\n}}'

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
                    "all": resolve_texture_path(textures['cube_all'], namespace, 'block', block_id)
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
                    texture_map[face] = resolve_texture_path(textures[key], namespace, 'block', block_id)

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
                texture_map[layer_key] = resolve_texture_path(textures[layer_key], namespace, 'item', item_id)

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

    own_entities = config.get('own_entities', [])
    for entity in own_entities:
        entity_id = entity['id']
        namespace = entity.get('namespace', config['modid'])
        names = entity.get('name', {})
        key = f'entity.{namespace}.{entity_id}'
        for lang_code, value in names.items():
            if lang_code not in lang_data:
                lang_data[lang_code] = {}
            lang_data[lang_code][key] = value
        # Spawn egg name
        egg_key = f'item.{namespace}.{entity_id}_spawn_egg'
        for lang_code, value in names.items():
            if lang_code not in lang_data:
                lang_data[lang_code] = {}
            lang_data[lang_code][egg_key] = f'{value} Spawn Egg' if lang_code == 'en_us' else f'{value}刷怪蛋'

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


def generate_item_mixins(config):
    """Generate Mixin classes for mixin items to modify attributes of existing items.
    Supports: max_stack, durability, rarity, enchantment_value
    """
    group = config['group']
    mixin_items = config.get('mixin_items', [])

    pkg_path = group.replace('.', '/')
    mixin_dir = f'src/main/java/{pkg_path}/mixin'
    os.makedirs(mixin_dir, exist_ok=True)

    # (attribute_key, method_name, return_type, value_transform, target_class, skip_default)
    ITEM_METHOD_MAP = [
        ('max_stack', 'getMaxStackSize', 'Integer', lambda v: str(v), 'ItemStack', lambda v: v == 64),
        ('durability', 'getMaxDamage', 'Integer', lambda v: str(v), 'ItemStack', lambda v: v == 0),
        ('rarity', 'getRarity', 'Rarity', lambda v: f'Rarity.{v.upper()}', 'ItemStack', lambda v: v.lower() == 'common'),
        ('enchantment_value', 'getEnchantmentValue', 'Integer', lambda v: str(v), 'Item', lambda v: v == 0),
    ]

    # Collect modifications per item, grouped by target class
    itemstack_modifications = []
    item_modifications = []

    for item in mixin_items:
        attrs = item.get('attributes', {})
        itemstack_mods = []
        item_mods = []
        for attr_key, method_name, return_type, transform, target_class, skip_default in ITEM_METHOD_MAP:
            if attr_key not in attrs:
                continue
            value = attrs[attr_key]
            if skip_default(value):
                continue
            java_value = transform(value)
            if target_class == 'ItemStack':
                itemstack_mods.append((method_name, return_type, java_value))
            else:
                item_mods.append((method_name, return_type, java_value))
        if itemstack_mods:
            itemstack_modifications.append((item, itemstack_mods))
        if item_mods:
            item_modifications.append((item, item_mods))

    # Generate ItemStackMixin
    if itemstack_modifications:
        class_name = 'ItemStackMixin'
        lines = [
            f'package {group}.mixin;',
            '',
            'import net.minecraft.core.registries.BuiltInRegistries;',
            'import net.minecraft.resources.ResourceLocation;',
            'import net.minecraft.world.item.Item;',
            'import net.minecraft.world.item.ItemStack;',
            'import net.minecraft.world.item.Rarity;',
            'import org.spongepowered.asm.mixin.Mixin;',
            'import org.spongepowered.asm.mixin.Shadow;',
            'import org.spongepowered.asm.mixin.injection.At;',
            'import org.spongepowered.asm.mixin.injection.Inject;',
            'import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;',
            '',
            '@Mixin(ItemStack.class)',
            f'public abstract class {class_name} {{',
            '',
            '    @Shadow',
            '    public abstract Item getItem();',
            ''
        ]

        generated_methods = set()
        for item, mods in itemstack_modifications:
            item_id = item['id']
            namespace = item.get('namespace', 'minecraft')
            item_key = f'{namespace}:{item_id}'

            for method_name, return_type, java_value in mods:
                method_key = f'{method_name}_{item_key}'
                if method_key in generated_methods:
                    continue
                generated_methods.add(method_key)

                inject_method_name = f'on{method_name[0].upper()}{method_name[1:]}_{namespace}_{item_id}'.replace('-', '_').replace('.', '_')
                cir_type = f'CallbackInfoReturnable<{return_type}>'

                lines.append(f'    @Inject(method = "{method_name}", at = @At("HEAD"), cancellable = true)')
                lines.append(f'    private void {inject_method_name}({cir_type} cir) {{')
                lines.append(f'        if (this.getItem() == BuiltInRegistries.ITEM.get(new ResourceLocation("{namespace}", "{item_id}"))) {{')
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
    else:
        # Clean up old ItemStackMixin if no longer needed
        old_path = f'{mixin_dir}/ItemStackMixin.java'
        if os.path.exists(old_path):
            os.remove(old_path)
            print(f"Removed old: {old_path}")

    # Generate ItemMixin
    if item_modifications:
        class_name = 'ItemMixin'
        lines = [
            f'package {group}.mixin;',
            '',
            'import net.minecraft.core.registries.BuiltInRegistries;',
            'import net.minecraft.resources.ResourceLocation;',
            'import net.minecraft.world.item.Item;',
            'import org.spongepowered.asm.mixin.Mixin;',
            'import org.spongepowered.asm.mixin.injection.At;',
            'import org.spongepowered.asm.mixin.injection.Inject;',
            'import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;',
            '',
            '@Mixin(Item.class)',
            f'public class {class_name} {{',
            ''
        ]

        generated_methods = set()
        for item, mods in item_modifications:
            item_id = item['id']
            namespace = item.get('namespace', 'minecraft')
            item_key = f'{namespace}:{item_id}'

            for method_name, return_type, java_value in mods:
                method_key = f'{method_name}_{item_key}'
                if method_key in generated_methods:
                    continue
                generated_methods.add(method_key)

                inject_method_name = f'on{method_name[0].upper()}{method_name[1:]}_{namespace}_{item_id}'.replace('-', '_').replace('.', '_')
                cir_type = f'CallbackInfoReturnable<{return_type}>'

                lines.append(f'    @Inject(method = "{method_name}", at = @At("HEAD"), cancellable = true)')
                lines.append(f'    private void {inject_method_name}({cir_type} cir) {{')
                lines.append(f'        if ((Item)(Object)this == BuiltInRegistries.ITEM.get(new ResourceLocation("{namespace}", "{item_id}"))) {{')
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
    else:
        # Clean up old ItemMixin if no longer needed
        old_path = f'{mixin_dir}/ItemMixin.java'
        if os.path.exists(old_path):
            os.remove(old_path)
            print(f"Removed old: {old_path}")

    # Register item mixins in modid.mixins.json
    mixins_json = f'src/main/resources/{config["modid"]}.mixins.json'
    if os.path.exists(mixins_json):
        with open(mixins_json, 'r', encoding='utf-8') as f:
            data = json.load(f)

        mixin_entries = data.get('mixins', [])
        has_itemstack = itemstack_modifications
        has_item = item_modifications

        if has_itemstack and 'ItemStackMixin' not in mixin_entries and f'{group}.mixin.ItemStackMixin' not in mixin_entries:
            mixin_entries.append('ItemStackMixin')
        if not has_itemstack and 'ItemStackMixin' in mixin_entries:
            mixin_entries.remove('ItemStackMixin')
        if has_item and 'ItemMixin' not in mixin_entries and f'{group}.mixin.ItemMixin' not in mixin_entries:
            mixin_entries.append('ItemMixin')
        if not has_item and 'ItemMixin' in mixin_entries:
            mixin_entries.remove('ItemMixin')

        data['mixins'] = mixin_entries
        with open(mixins_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Updated: {mixins_json}")

    # Print hints for unsupported attributes
    print("\n[Mixin Items - Auto & Manual Attributes]")
    auto_attrs = {m[0] for m in ITEM_METHOD_MAP}
    for item in mixin_items:
        item_id = item['id']
        namespace = item.get('namespace', 'minecraft')
        attrs = item.get('attributes', {})
        unsupported = []
        for key, value in attrs.items():
            if key in auto_attrs:
                continue
            if value and value != 0 and value != 64 and value != False:
                if key != 'rarity' or (isinstance(value, str) and value.lower() != 'common'):
                    unsupported.append(f"{key} = {value}")
        if unsupported:
            print(f"  - {namespace}:{item_id} needs manual Mixin for:")
            for u in unsupported:
                print(f"      {u}")
        food = item.get('food')
        if food:
            print(f"  - {namespace}:{item_id} has custom food that requires manual Mixin.")
    print("[End Mixin Item Hints]\n")


def generate_entities(config):
    """Generate entity classes, ModEntities.java, client renderers, and copy textures."""
    import shutil
    import re
    modid = config['modid']
    group = config['group']
    entities = config.get('own_entities', [])

    pkg_path = group.replace('.', '/')
    entity_dir = f'src/main/java/{pkg_path}/entity'
    os.makedirs(entity_dir, exist_ok=True)

    if not entities:
        # Clean up all entity Java files
        if os.path.exists(entity_dir):
            for fname in os.listdir(entity_dir):
                if fname.endswith('.java'):
                    old_path = os.path.join(entity_dir, fname)
                    os.remove(old_path)
                    print(f"Removed old: {old_path}")
            # Remove empty entity dir
            try:
                os.rmdir(entity_dir)
                print(f"Removed empty dir: {entity_dir}")
            except OSError:
                pass
        # Clean up client renderer registrations
        client_mod_file = f'src/client/java/{pkg_path}/client/ExampleModClient.java'
        if os.path.exists(client_mod_file):
            with open(client_mod_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Remove EntityRendererRegistry.register lines and associated blocks
            import re
            # Remove renderer register blocks: EntityRendererRegistry.register(ModEntities.XXX, context -> ...);
            content = re.sub(
                r'\s+EntityRendererRegistry\.register\(ModEntities\.\w+,\s*context\s*->\s*new MobRenderer<[^>]+>\(context,\s*new CowModel<>\(context\.bakeLayer\(ModelLayers\.COW\)\),\s*0\.5f\)\s*\{\s*@Override\s*public ResourceLocation getTextureLocation\([^)]+\)\s*\{\s*return new ResourceLocation\("[^"]+",\s*"textures/entity/[^"]+"\);\s*\}\s*\}\s*\);',
                '',
                content,
                flags=re.DOTALL
            )
            # Also remove simpler form without the inline class
            content = re.sub(
                r'\s+EntityRendererRegistry\.register\(ModEntities\.\w+,\s*[^;]+\);',
                '',
                content,
                flags=re.DOTALL
            )
            # Remove unused imports if no renderer left
            if 'EntityRendererRegistry' not in content:
                content = re.sub(r'import net\.fabricmc\.fabric\.api\.client\.rendering\.v1\.EntityRendererRegistry;\n', '', content)
                content = re.sub(r'import net\.minecraft\.client\.model\.CowModel;\n', '', content)
                content = re.sub(r'import net\.minecraft\.client\.model\.EntityModel;\n', '', content)
                content = re.sub(r'import net\.minecraft\.client\.model\.geom\.ModelLayers;\n', '', content)
                content = re.sub(r'import net\.minecraft\.client\.renderer\.entity\.MobRenderer;\n', '', content)
                content = re.sub(r'import net\.minecraft\.resources\.ResourceLocation;\n', '', content)
            # Remove ModEntities import if no longer used
            if 'ModEntities.' not in content:
                content = re.sub(rf'import {re.escape(group)}\.entity\.ModEntities;\n', '', content)
            with open(client_mod_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Cleaned renderers: {client_mod_file}")
        # Remove ModEntities import from ExampleMod.java
        mod_file = f'src/main/java/{pkg_path}/ExampleMod.java'
        if os.path.exists(mod_file):
            with open(mod_file, 'r', encoding='utf-8') as f:
                content = f.read()
            content = re.sub(rf'import {re.escape(group)}\.entity\.ModEntities;\n', '', content)
            content = re.sub(r'\s+ModEntities\.register\(\);', '', content)
            with open(mod_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Cleaned ModEntities: {mod_file}")
        return

    BASE_CATEGORY = {
        'mob': 'MISC',
        'animal': 'CREATURE',
        'monster': 'MONSTER',
        'water_animal': 'WATER_CREATURE',
        'ambient': 'AMBIENT',
        'flying': 'CREATURE',
    }

    BASE_CLASS = {
        'mob': ('Mob', 'net.minecraft.world.entity.Mob'),
        'animal': ('Animal', 'net.minecraft.world.entity.animal.Animal'),
        'monster': ('Monster', 'net.minecraft.world.entity.monster.Monster'),
        'water_animal': ('WaterAnimal', 'net.minecraft.world.entity.animal.WaterAnimal'),
        'ambient': ('AmbientCreature', 'net.minecraft.world.entity.ambient.AmbientCreature'),
        'flying': ('FlyingMob', 'net.minecraft.world.entity.FlyingMob'),
    }

    # Generate individual entity classes
    for entity in entities:
        entity_id = entity['id']
        class_name = pascal_case(entity_id)
        attrs = entity.get('attributes', {})
        hitbox = entity.get('hitbox', {})
        base = entity.get('base', 'mob').lower()

        health = attrs.get('health', 20)
        speed = attrs.get('movement_speed', 0.25)
        damage = attrs.get('attack_damage', 3)
        follow_range = attrs.get('follow_range', 16)

        width = hitbox.get('width', 0.6)
        height = hitbox.get('height', 1.8)

        parent_info = BASE_CLASS.get(base, ('Mob', 'net.minecraft.world.entity.Mob'))
        parent_class = parent_info[0]
        parent_import = parent_info[1]

        ai = entity.get('ai', {})
        goals = ai.get('goals', [])
        targets = ai.get('targets', [])

        # Collect imports for AI goals
        goal_imports = set()
        goal_lines = []
        target_lines = []

        GOAL_MAP = {
            'swim': ('FloatGoal', 'this'),
            'panic': ('PanicGoal', 'this, {speed}'),
            'wander': ('RandomStrollGoal', 'this, {speed}'),
            'water_avoiding_wander': ('WaterAvoidingRandomStrollGoal', 'this, {speed}'),
            'look_at_player': ('LookAtPlayerGoal', 'this, {entity_class}.class, {distance}f'),
            'look_at_entity': ('LookAtPlayerGoal', 'this, {entity_class}.class, {distance}f'),
            'look_randomly': ('RandomLookAroundGoal', 'this'),
            'attack_melee': ('MeleeAttackGoal', 'this, {speed}, {follow}'),
            'breed': ('BreedGoal', 'this, {speed}'),
            'follow_parent': ('FollowParentGoal', 'this, {speed}'),
            'tempt': ('TemptGoal', 'this, {speed}, {ingredient}, {can_scare}'),
            'float': ('FloatGoal', 'this'),
            'jump_when_chased': ('PanicGoal', 'this, {speed}'),
            'avoid_entity': ('AvoidEntityGoal', 'this, {entity_class}.class, {distance}, {far_speed}, {near_speed}'),
        }

        TARGET_MAP = {
            'nearest_attackable': ('NearestAttackableTargetGoal', 'this, {target_class}.class, {check_visibility}'),
            'hurt_by_target': ('HurtByTargetGoal', 'this'),
        }

        for goal in goals:
            gtype = goal.get('type', '')
            priority = goal.get('priority', 0)
            info = GOAL_MAP.get(gtype)
            if not info:
                continue
            cls_name, template = info
            if cls_name in ('FloatGoal', 'PanicGoal', 'RandomStrollGoal', 'WaterAvoidingRandomStrollGoal',
                            'LookAtPlayerGoal', 'MeleeAttackGoal', 'BreedGoal', 'FollowParentGoal',
                            'TemptGoal', 'AvoidEntityGoal'):
                goal_imports.add(f'net.minecraft.world.entity.ai.goal.{cls_name}')
            params = template
            if '{speed}' in params:
                params = params.replace('{speed}', str(goal.get('speed', speed)))
            if '{distance}' in params:
                params = params.replace('{distance}', str(goal.get('distance', 6.0)))
            if '{follow}' in params:
                params = params.replace('{follow}', 'true' if goal.get('follow_even_if_not_seen', False) else 'false')
            if '{entity_class}' in params:
                entity_cls = goal.get('entity_class', 'Player')
                params = params.replace('{entity_class}', entity_cls)
                if entity_cls == 'Player':
                    goal_imports.add('net.minecraft.world.entity.player.Player')
            if '{ingredient}' in params:
                ingredient = goal.get('ingredient', '')
                if ingredient:
                    ns, name = ingredient.split(':', 1) if ':' in ingredient else ('minecraft', ingredient)
                    params = params.replace('{ingredient}', f'Ingredient.of(Items.{name.upper()})')
                    goal_imports.add('net.minecraft.world.item.crafting.Ingredient')
                    goal_imports.add('net.minecraft.world.item.Items')
                else:
                    params = params.replace('{ingredient}', 'Ingredient.EMPTY')
                    goal_imports.add('net.minecraft.world.item.crafting.Ingredient')
            if '{can_scare}' in params:
                params = params.replace('{can_scare}', 'true' if goal.get('can_scare_by_player_movement', False) else 'false')
            if '{far_speed}' in params:
                far_speed = goal.get('far_speed', speed * 1.5)
                near_speed = goal.get('near_speed', speed * 1.0)
                params = params.replace('{far_speed}', str(far_speed)).replace('{near_speed}', str(near_speed))

            goal_lines.append(f'        this.goalSelector.addGoal({priority}, new {cls_name}({params}));')

        for target in targets:
            ttype = target.get('type', '')
            priority = target.get('priority', 0)
            info = TARGET_MAP.get(ttype)
            if not info:
                continue
            cls_name, template = info
            if cls_name in ('NearestAttackableTargetGoal', 'HurtByTargetGoal'):
                goal_imports.add(f'net.minecraft.world.entity.ai.goal.target.{cls_name}')
            params = template
            if '{target_class}' in params:
                target_cls = target.get('target_class', 'Player')
                params = params.replace('{target_class}', target_cls)
                if target_cls == 'Player':
                    goal_imports.add('net.minecraft.world.entity.player.Player')
            if '{check_visibility}' in params:
                params = params.replace('{check_visibility}', 'true' if target.get('check_visibility', True) else 'false')

            if cls_name == 'NearestAttackableTargetGoal':
                target_lines.append(f'        this.targetSelector.addGoal({priority}, new {cls_name}<>({params}));')
            else:
                target_lines.append(f'        this.targetSelector.addGoal({priority}, new {cls_name}({params}));')

        lines = [
            f'package {group}.entity;',
            '',
            'import net.minecraft.world.entity.EntityType;',
            f'import {parent_import};',
        ]
        for imp in sorted(goal_imports):
            lines.append(f'import {imp};')
        lines.extend([
            'import net.minecraft.world.entity.ai.attributes.AttributeSupplier;',
            'import net.minecraft.world.entity.ai.attributes.Attributes;',
            'import net.minecraft.world.level.Level;',
            '',
            f'public class {class_name} extends {parent_class} {{',
            '',
            f'    public {class_name}(EntityType<{class_name}> entityType, Level level) {{',
            '        super(entityType, level);',
            '    }',
            '',
            '    @Override',
            '    protected void registerGoals() {',
            '        super.registerGoals();',
        ])
        if goal_lines:
            lines.extend(goal_lines)
        else:
            lines.append('        // No goals configured')
        if target_lines:
            lines.extend(target_lines)
        lines.append('    }')
        lines.append('')
        lines.append('    public static AttributeSupplier.Builder createAttributes() {')
        if parent_class == 'Mob':
            lines.append('        return Mob.createMobAttributes()')
        elif parent_class == 'Animal':
            lines.append('        return Animal.createMobAttributes()')
        elif parent_class == 'Monster':
            lines.append('        return Monster.createMonsterAttributes()')
        elif parent_class == 'WaterAnimal':
            lines.append('        return WaterAnimal.createMobAttributes()')
        elif parent_class == 'AmbientCreature':
            lines.append('        return AmbientCreature.createMobAttributes()')
        elif parent_class == 'FlyingMob':
            lines.append('        return FlyingMob.createMobAttributes()')
        else:
            lines.append('        return Mob.createMobAttributes()')

        lines.append(f'            .add(Attributes.MAX_HEALTH, {health})')
        lines.append(f'            .add(Attributes.MOVEMENT_SPEED, {speed})')
        if damage != 0:
            lines.append(f'            .add(Attributes.ATTACK_DAMAGE, {damage})')
        lines.append(f'            .add(Attributes.FOLLOW_RANGE, {follow_range});')
        lines.append('    }')

        # Traits
        traits = entity.get('traits', {})
        trait_methods = []
        trait_imports = set()

        if traits.get('fire_immune'):
            trait_methods.extend([
                '',
                '    @Override',
                '    public boolean fireImmune() {',
                '        return true;',
                '    }',
            ])

        if traits.get('immune_to_fall'):
            trait_imports.add('net.minecraft.world.damagesource.DamageSource')
            trait_methods.extend([
                '',
                '    @Override',
                '    public boolean causeFallDamage(float f, float g, DamageSource damageSource) {',
                '        return false;',
                '    }',
            ])

        if traits.get('immune_to_drowning'):
            trait_methods.extend([
                '',
                '    @Override',
                '    protected int decreaseAirSupply(int i) {',
                '        return i;',
                '    }',
            ])

        if traits.get('immune_to_suffocation'):
            trait_methods.extend([
                '',
                '    @Override',
                '    public boolean isInWall() {',
                '        return false;',
                '    }',
            ])

        if traits.get('is_pushed_by_fluids') is False:
            trait_methods.extend([
                '',
                '    @Override',
                '    public boolean isPushedByFluid() {',
                '        return false;',
                '    }',
            ])

        if traits.get('can_be_leashed'):
            trait_imports.add('net.minecraft.world.entity.player.Player')
            trait_methods.extend([
                '',
                '    @Override',
                '    public boolean canBeLeashed(Player player) {',
                '        return true;',
                '    }',
            ])

        if traits.get('persistent'):
            trait_methods.extend([
                '',
                '    @Override',
                '    public boolean requiresCustomPersistence() {',
                '        return true;',
                '    }',
            ])

        # Sounds
        sounds = entity.get('sounds', {})
        sound_methods = []
        sound_imports = set()

        if sounds.get('ambient'):
            sound_imports.add('net.minecraft.sounds.SoundEvent')
            sound_imports.add('net.minecraft.core.registries.BuiltInRegistries')
            sound_imports.add('net.minecraft.resources.ResourceLocation')
            ambient = sounds['ambient']
            ns, name = ambient.split(':', 1) if ':' in ambient else ('minecraft', ambient)
            sound_methods.extend([
                '',
                '    @Override',
                '    protected SoundEvent getAmbientSound() {',
                f'        return BuiltInRegistries.SOUND_EVENT.get(new ResourceLocation("{ns}", "{name}"));',
                '    }',
            ])

        if sounds.get('hurt'):
            sound_imports.add('net.minecraft.sounds.SoundEvent')
            sound_imports.add('net.minecraft.world.damagesource.DamageSource')
            sound_imports.add('net.minecraft.core.registries.BuiltInRegistries')
            sound_imports.add('net.minecraft.resources.ResourceLocation')
            hurt = sounds['hurt']
            ns, name = hurt.split(':', 1) if ':' in hurt else ('minecraft', hurt)
            sound_methods.extend([
                '',
                '    @Override',
                '    protected SoundEvent getHurtSound(DamageSource damageSource) {',
                f'        return BuiltInRegistries.SOUND_EVENT.get(new ResourceLocation("{ns}", "{name}"));',
                '    }',
            ])

        if sounds.get('death'):
            sound_imports.add('net.minecraft.sounds.SoundEvent')
            sound_imports.add('net.minecraft.core.registries.BuiltInRegistries')
            sound_imports.add('net.minecraft.resources.ResourceLocation')
            death = sounds['death']
            ns, name = death.split(':', 1) if ':' in death else ('minecraft', death)
            sound_methods.extend([
                '',
                '    @Override',
                '    protected SoundEvent getDeathSound() {',
                f'        return BuiltInRegistries.SOUND_EVENT.get(new ResourceLocation("{ns}", "{name}"));',
                '    }',
            ])

        if sounds.get('step'):
            sound_imports.add('net.minecraft.sounds.SoundEvent')
            sound_imports.add('net.minecraft.core.registries.BuiltInRegistries')
            sound_imports.add('net.minecraft.resources.ResourceLocation')
            sound_imports.add('net.minecraft.core.BlockPos')
            sound_imports.add('net.minecraft.world.level.block.state.BlockState')
            step = sounds['step']
            ns, name = step.split(':', 1) if ':' in step else ('minecraft', step)
            sound_methods.extend([
                '',
                '    @Override',
                '    protected void playStepSound(BlockPos blockPos, BlockState blockState) {',
                f'        this.playSound(BuiltInRegistries.SOUND_EVENT.get(new ResourceLocation("{ns}", "{name}")), 0.15F, 1.0F);',
                '    }',
            ])

        # can_pick_up_loot: set in constructor
        constructor_extra = []
        if traits.get('can_pick_up_loot'):
            constructor_extra.append('        this.setCanPickUpLoot(true);')

        # Rebuild lines with imports, constructor, and all methods
        all_imports = set(goal_imports) | trait_imports | sound_imports
        lines = [
            f'package {group}.entity;',
            '',
            'import net.minecraft.world.entity.EntityType;',
            f'import {parent_import};',
        ]
        for imp in sorted(all_imports):
            lines.append(f'import {imp};')
        lines.extend([
            'import net.minecraft.world.entity.ai.attributes.AttributeSupplier;',
            'import net.minecraft.world.entity.ai.attributes.Attributes;',
            'import net.minecraft.world.level.Level;',
            '',
            f'public class {class_name} extends {parent_class} {{',
            '',
            f'    public {class_name}(EntityType<{class_name}> entityType, Level level) {{',
            '        super(entityType, level);',
        ])
        if constructor_extra:
            lines.extend(constructor_extra)
        lines.extend([
            '    }',
            '',
            '    @Override',
            '    protected void registerGoals() {',
            '        super.registerGoals();',
        ])
        if goal_lines:
            lines.extend(goal_lines)
        else:
            lines.append('        // No goals configured')
        if target_lines:
            lines.extend(target_lines)
        lines.append('    }')
        lines.append('')
        lines.append('    public static AttributeSupplier.Builder createAttributes() {')
        if parent_class == 'Mob':
            lines.append('        return Mob.createMobAttributes()')
        elif parent_class == 'Animal':
            lines.append('        return Animal.createMobAttributes()')
        elif parent_class == 'Monster':
            lines.append('        return Monster.createMonsterAttributes()')
        elif parent_class == 'WaterAnimal':
            lines.append('        return WaterAnimal.createMobAttributes()')
        elif parent_class == 'AmbientCreature':
            lines.append('        return AmbientCreature.createMobAttributes()')
        elif parent_class == 'FlyingMob':
            lines.append('        return FlyingMob.createMobAttributes()')
        else:
            lines.append('        return Mob.createMobAttributes()')

        lines.append(f'            .add(Attributes.MAX_HEALTH, {health})')
        lines.append(f'            .add(Attributes.MOVEMENT_SPEED, {speed})')
        if damage != 0:
            lines.append(f'            .add(Attributes.ATTACK_DAMAGE, {damage})')
        lines.append(f'            .add(Attributes.FOLLOW_RANGE, {follow_range});')
        lines.append('    }')

        # Animal is abstract and requires getBreedOffspring and isFood
        breeding = entity.get('breeding', {})
        breeding_foods = breeding.get('food', [])

        if parent_class == 'Animal':
            lines.extend([
                '',
                '    @Override',
                '    @SuppressWarnings("unchecked")',
                '    public net.minecraft.world.entity.AgeableMob getBreedOffspring(net.minecraft.server.level.ServerLevel serverLevel, net.minecraft.world.entity.AgeableMob ageableMob) {',
                f'        return new {class_name}((EntityType<{class_name}>) this.getType(), this.level());',
                '    }',
                '',
                '    @Override',
                '    public boolean isFood(net.minecraft.world.item.ItemStack itemStack) {',
            ])
            if breeding_foods:
                food_checks = []
                for food in breeding_foods:
                    ns, name = food.split(':', 1) if ':' in food else ('minecraft', food)
                    food_checks.append(f'itemStack.is(net.minecraft.core.registries.BuiltInRegistries.ITEM.get(new net.minecraft.resources.ResourceLocation("{ns}", "{name}")))')
                lines.append(f'        return {" || ".join(food_checks)};')
            else:
                lines.append('        return false;')
            lines.extend([
                '    }',
            ])

        # Drops
        drops = entity.get('drops', [])
        drop_methods = []
        drop_imports = set()
        if drops:
            drop_imports.add('net.minecraft.world.damagesource.DamageSource')
            drop_imports.add('net.minecraft.world.item.ItemStack')
            drop_imports.add('net.minecraft.core.registries.BuiltInRegistries')
            drop_imports.add('net.minecraft.resources.ResourceLocation')
            drop_lines = [
                '',
                '    @Override',
                '    protected void dropCustomDeathLoot(DamageSource damageSource, int lootingLevel, boolean hitByPlayer) {',
                '        super.dropCustomDeathLoot(damageSource, lootingLevel, hitByPlayer);',
            ]
            for drop in drops:
                drop_id = drop.get('id', '')
                if not drop_id:
                    continue
                ns, name = drop_id.split(':', 1) if ':' in drop_id else ('minecraft', drop_id)
                count = drop.get('count', 1)
                looting_bonus = drop.get('looting_bonus', 0)
                chance = drop.get('chance', 1.0)

                if isinstance(count, dict):
                    min_count = count.get('min', 0)
                    max_count = count.get('max', 1)
                    if min_count == 0:
                        count_expr = f'this.random.nextInt({max_count - min_count + 1})'
                    else:
                        count_expr = f'this.random.nextInt({max_count - min_count + 1}) + {min_count}'
                else:
                    count_expr = str(int(count))

                if looting_bonus > 0:
                    count_expr = f'{count_expr} + this.random.nextInt(lootingLevel * {looting_bonus} + 1)'

                if chance < 1.0:
                    drop_lines.append(f'        if (this.random.nextFloat() < {chance}f) {{')
                    indent = '            '
                else:
                    indent = '        '

                drop_lines.append(f'{indent}this.spawnAtLocation(new ItemStack(BuiltInRegistries.ITEM.get(new ResourceLocation("{ns}", "{name}")), {count_expr}));')

                if chance < 1.0:
                    drop_lines.append('        }')

            drop_lines.append('    }')
            drop_methods.extend(drop_lines)

        # Particles
        particles = entity.get('particles', {})
        particle_methods = []
        particle_imports = set()
        if particles.get('ambient'):
            ambient_particle = particles['ambient']
            ptype = ambient_particle.get('type', '')
            pchance = ambient_particle.get('chance', 0.01)
            if ptype:
                particle_imports.add('net.minecraft.server.level.ServerLevel')
                particle_imports.add('net.minecraft.core.registries.BuiltInRegistries')
                particle_imports.add('net.minecraft.resources.ResourceLocation')
                particle_imports.add('net.minecraft.core.particles.ParticleOptions')
                ns, name = ptype.split(':', 1) if ':' in ptype else ('minecraft', ptype)
                particle_methods.extend([
                    '',
                    '    @Override',
                    '    public void tick() {',
                    '        super.tick();',
                    f'        if (!this.level().isClientSide() && this.random.nextFloat() < {pchance}f) {{',
                    f'            ((ServerLevel) this.level()).sendParticles((ParticleOptions) BuiltInRegistries.PARTICLE_TYPE.get(new ResourceLocation("{ns}", "{name}")),',
                    '                this.getX(), this.getY() + this.getBbHeight() / 2.0, this.getZ(),',
                    '                1, 0.2, 0.2, 0.2, 0.0);',
                    '        }',
                    '    }',
                ])

        # Merge all extra imports
        all_imports = set(goal_imports) | trait_imports | sound_imports | drop_imports | particle_imports
        # Rebuild import section in lines
        import_section = [
            f'package {group}.entity;',
            '',
            'import net.minecraft.world.entity.EntityType;',
            f'import {parent_import};',
        ]
        for imp in sorted(all_imports):
            import_section.append(f'import {imp};')
        import_section.extend([
            'import net.minecraft.world.entity.ai.attributes.AttributeSupplier;',
            'import net.minecraft.world.entity.ai.attributes.Attributes;',
            'import net.minecraft.world.level.Level;',
            '',
        ])
        # Replace the import section in lines (first N lines)
        # Find where the class declaration starts
        class_decl_idx = None
        for i, line in enumerate(lines):
            if line.startswith(f'public class {class_name}'):
                class_decl_idx = i
                break
        if class_decl_idx is not None:
            lines = import_section + lines[class_decl_idx:]

        if trait_methods:
            lines.extend(trait_methods)
        if sound_methods:
            lines.extend(sound_methods)
        if drop_methods:
            lines.extend(drop_methods)
        # Taming stub
        taming = entity.get('taming', {})
        if taming.get('enabled'):
            lines.extend([
                '',
                '    // TODO: Taming logic - override mobInteract() to handle taming item usage',
                f'    // Taming item: {taming.get("item", "")}, chance: {taming.get("tame_chance", 0.33)}',
            ])

        # Rideable stub
        rideable = entity.get('rideable', {})
        if rideable.get('enabled'):
            lines.extend([
                '',
                '    // TODO: Rideable logic - override getControllingPassenger(), travel(), canBeControlledByRider()',
                f'    // Saddle required: {rideable.get("saddle_required", False)}, can control: {rideable.get("can_control", True)}, ridden speed: {rideable.get("ridden_speed", 0.35)}',
            ])

        if particle_methods:
            lines.extend(particle_methods)

        lines.append('')
        lines.append('}')

        path = os.path.join(entity_dir, f'{class_name}.java')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"Generated: {path}")

    # Generate ModEntities.java
    mod_lines = [
        f'package {group}.entity;',
        '',
        'import net.fabricmc.fabric.api.biome.v1.BiomeModifications;',
        'import net.fabricmc.fabric.api.biome.v1.BiomeSelectors;',
        'import net.fabricmc.fabric.api.object.builder.v1.entity.FabricDefaultAttributeRegistry;',
        'import net.minecraft.core.Registry;',
        'import net.minecraft.core.registries.BuiltInRegistries;',
        'import net.minecraft.core.registries.Registries;',
        'import net.minecraft.resources.ResourceKey;',
        'import net.minecraft.resources.ResourceLocation;',
        'import net.minecraft.world.entity.EntityType;',
        'import net.minecraft.world.entity.MobCategory;',
        'import net.minecraft.world.item.Item;',
        'import net.minecraft.world.item.SpawnEggItem;',
    ]

    # Check if any entity uses biome tags
    has_biome_tags = any(
        any(b.startswith('#') for b in e.get('spawn', {}).get('biomes', []))
        for e in entities
    )
    if has_biome_tags:
        mod_lines.append('import net.minecraft.tags.TagKey;')

    mod_lines.extend([
        '',
        'public class ModEntities {',
        ''
    ])

    for entity in entities:
        class_name = pascal_case(entity['id'])
        field_name = const_case(entity['id'])
        mod_lines.append(f'    public static EntityType<{class_name}> {field_name};')
        mod_lines.append(f'    public static Item {field_name}_SPAWN_EGG;')

    mod_lines.append('')
    mod_lines.append('    public static void register() {')

    for entity in entities:
        entity_id = entity['id']
        class_name = pascal_case(entity_id)
        field_name = const_case(entity_id)
        base = entity.get('base', 'mob')
        category = BASE_CATEGORY.get(base.lower(), 'MISC')
        hitbox = entity.get('hitbox', {})
        width = hitbox.get('width', 0.6)
        height = hitbox.get('height', 1.8)

        mod_lines.append(f'        {field_name} = Registry.register(')
        mod_lines.append('            BuiltInRegistries.ENTITY_TYPE,')
        mod_lines.append(f'            new ResourceLocation("{modid}", "{entity_id}"),')
        mod_lines.append(f'            EntityType.Builder.of({class_name}::new, MobCategory.{category})')
        mod_lines.append(f'                .sized({width}f, {height}f)')
        mod_lines.append('                .build()')
        mod_lines.append('        );')
        mod_lines.append('')
        mod_lines.append(f'        FabricDefaultAttributeRegistry.register({field_name}, {class_name}.createAttributes());')
        mod_lines.append('')

        spawn = entity.get('spawn', {})
        color1 = spawn.get('egg_color1', 0xA0522D)
        color2 = spawn.get('egg_color2', 0xFFFFFF)
        mod_lines.append(f'        {field_name}_SPAWN_EGG = Registry.register(')
        mod_lines.append('            BuiltInRegistries.ITEM,')
        mod_lines.append(f'            new ResourceLocation("{modid}", "{entity_id}_spawn_egg"),')
        mod_lines.append(f'            new SpawnEggItem({field_name}, {color1}, {color2}, new Item.Properties())')
        mod_lines.append('        );')
        mod_lines.append('')

        if spawn.get('enabled', True):
            weight = spawn.get('weight', 10)
            min_count = spawn.get('min_count', 1)
            max_count = spawn.get('max_count', 4)
            biomes = spawn.get('biomes', [])

            biome_keys = []
            biome_tags = []
            for biome in biomes:
                if biome.startswith('#'):
                    biome_tags.append(biome[1:])
                else:
                    biome_keys.append(biome)

            selectors = []
            if biome_keys:
                key_entries = []
                for b in biome_keys:
                    ns, name = b.split(':', 1) if ':' in b else ('minecraft', b)
                    key_entries.append(f'ResourceKey.create(Registries.BIOME, new ResourceLocation("{ns}", "{name}"))')
                selectors.append('BiomeSelectors.includeByKey(\n                ' + ',\n                '.join(key_entries) + '\n            )')

            if biome_tags:
                tag_entries = []
                for b in biome_tags:
                    ns, name = b.split(':', 1) if ':' in b else ('minecraft', b)
                    tag_entries.append(f'TagKey.create(Registries.BIOME, new ResourceLocation("{ns}", "{name}"))')
                if len(tag_entries) == 1:
                    selectors.append(f'BiomeSelectors.tag({tag_entries[0]})')
                else:
                    selectors.append(f'BiomeSelectors.tag({tag_entries[0]})' + ''.join(f'.or(BiomeSelectors.tag({t}))' for t in tag_entries[1:]))

            if selectors:
                if len(selectors) == 1:
                    selector_expr = selectors[0]
                else:
                    selector_expr = selectors[0] + ''.join(f'.or({s})' for s in selectors[1:])

                mod_lines.append(f'        BiomeModifications.addSpawn(')
                mod_lines.append(f'            {selector_expr},')
                mod_lines.append(f'            MobCategory.{category},')
                mod_lines.append(f'            {field_name},')
                mod_lines.append(f'            {weight}, {min_count}, {max_count}')
                mod_lines.append('        );')
                mod_lines.append('')

    mod_lines.append('    }')
    mod_lines.append('}')

    path = os.path.join(entity_dir, 'ModEntities.java')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(mod_lines))
    print(f"Generated: {path}")

    # Update client renderers
    client_mod_file = f'src/client/java/{pkg_path}/client/ExampleModClient.java'
    if os.path.exists(client_mod_file):
        with open(client_mod_file, 'r', encoding='utf-8') as f:
            content = f.read()

        import_entity = f'import {group}.entity.ModEntities;'
        if import_entity not in content:
            if 'import ' in content:
                content = content.replace('import ', f'{import_entity}\nimport ', 1)
            else:
                content = content.replace('package ', f'{import_entity}\n\npackage ', 1)

        imports_needed = [
            'import net.fabricmc.fabric.api.client.rendering.v1.EntityRendererRegistry;',
            'import net.minecraft.client.model.CowModel;',
            'import net.minecraft.client.model.geom.ModelLayers;',
            'import net.minecraft.client.renderer.entity.MobRenderer;',
            'import net.minecraft.resources.ResourceLocation;',
        ]
        for imp in imports_needed:
            if imp not in content:
                content = content.replace('import ', f'{imp}\nimport ', 1)

        for entity in entities:
            entity_id = entity['id']
            class_name = pascal_case(entity_id)
            field_name = const_case(entity_id)

            # Import the entity class itself
            entity_import = f'import {group}.entity.{class_name};'
            if entity_import not in content:
                content = content.replace('import ', f'{entity_import}\nimport ', 1)

            reg_marker = f'EntityRendererRegistry.register(ModEntities.{field_name}'
            if reg_marker in content:
                continue

            renderer_block = f'''        EntityRendererRegistry.register(ModEntities.{field_name}, context ->
            new MobRenderer<{class_name}, CowModel<{class_name}>>(context, new CowModel<>(context.bakeLayer(ModelLayers.COW)), 0.5f) {{
                @Override
                public ResourceLocation getTextureLocation({class_name} entity) {{
                    return new ResourceLocation("{modid}", "textures/entity/{entity_id}.png");
                }}
            }}
        );'''

            idx = content.find('public void onInitializeClient()')
            if idx != -1:
                brace_idx = content.find('{', idx)
                if brace_idx != -1:
                    content = content[:brace_idx + 1] + '\n' + renderer_block + content[brace_idx + 1:]

        # Clean up unused imports after all renderers are processed
        if 'EntityRendererRegistry' not in content:
            content = re.sub(r'import net\.fabricmc\.fabric\.api\.client\.rendering\.v1\.EntityRendererRegistry;\n', '', content)
            content = re.sub(r'import net\.minecraft\.client\.model\.CowModel;\n', '', content)
            content = re.sub(r'import net\.minecraft\.client\.model\.geom\.ModelLayers;\n', '', content)
            content = re.sub(r'import net\.minecraft\.client\.renderer\.entity\.MobRenderer;\n', '', content)
            content = re.sub(r'import net\.minecraft\.resources\.ResourceLocation;\n', '', content)
        # EntityModel is no longer used in our renderer blocks; always clean it
        content = re.sub(r'import net\.minecraft\.client\.model\.EntityModel;\n', '', content)
        if 'ModEntities.' not in content:
            content = re.sub(rf'import {re.escape(group)}\.entity\.ModEntities;\n', '', content)
        # Also remove entity class imports if no renderers reference them
        for entity in entities:
            class_name = pascal_case(entity['id'])
            if class_name not in content:
                content = re.sub(rf'import {re.escape(group)}\.entity\.{class_name};\n', '', content)

        with open(client_mod_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {client_mod_file}")

    # Copy entity textures
    for entity in entities:
        entity_id = entity['id']
        textures = entity.get('textures', {})
        if 'entity' in textures:
            val = textures['entity']
            if val.startswith('./'):
                src_path = val[2:]
                if not src_path.endswith('.png'):
                    src_path += '.png'
                target_dir = f'src/main/resources/assets/{modid}/textures/entity'
                target_path = os.path.join(target_dir, f'{entity_id}.png')
                if os.path.exists(src_path):
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.copy2(src_path, target_path)
                    print(f"Copied texture: {src_path} -> {target_path}")


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


def resolve_texture_path(val, namespace, asset_type, asset_id):
    """Resolve a texture path from config.

    Paths starting with './' are treated as relative to the mod project root
    and the referenced image is copied into the resource directory.
    Other paths are treated as direct resource references (legacy format).
    """
    import shutil

    if val.startswith('./'):
        src_path = val[2:]
        if not src_path.endswith('.png'):
            src_path += '.png'

        target_dir = f'src/main/resources/assets/{namespace}/textures/{asset_type}'
        target_path = os.path.join(target_dir, f'{asset_id}.png')

        if os.path.exists(src_path):
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(src_path, target_path)
            print(f"Copied texture: {src_path} -> {target_path}")
        else:
            print(f"Warning: texture source not found: {src_path}")

        return f'{namespace}:{asset_type}/{asset_id}'

    # Legacy format: assets/modid/textures/...  ->  modid:...
    val = val.replace('assets/', '').replace('/textures', '')
    val = val.replace(f'/block/', ':block/').replace(f'/item/', ':item/')
    return val


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


def compute_input_hash(main_config):
    """Compute a SHA-256 hash of all config files referenced in main_config['files']."""
    hasher = hashlib.sha256()
    base_dir = 'createamod'
    files_config = main_config.get('files', [])

    matched_files = set()
    if isinstance(files_config, dict):
        for pattern in files_config.values():
            search_path = os.path.join(base_dir, '**', pattern)
            for fp in glob.glob(search_path, recursive=True):
                fp = os.path.normpath(fp)
                if os.path.basename(fp).lower() != 'config.createamod.json':
                    matched_files.add(fp)
    else:
        for pattern in files_config:
            search_path = os.path.join(base_dir, '**', pattern)
            for fp in glob.glob(search_path, recursive=True):
                fp = os.path.normpath(fp)
                if os.path.basename(fp).lower() != 'config.createamod.json':
                    matched_files.add(fp)

    # Also include the main config itself
    main_path = MAIN_CONFIG_PATH
    if os.path.exists(main_path):
        matched_files.add(main_path)

    for fpath in sorted(matched_files):
        try:
            with open(fpath, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    hasher.update(chunk)
        except Exception:
            pass

        # Also hash referenced texture images
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            textures = data.get('textures', {})
            for tex_val in textures.values():
                if isinstance(tex_val, str) and tex_val.startswith('./'):
                    img_path = tex_val[2:]
                    if not img_path.endswith('.png'):
                        img_path += '.png'
                    if os.path.exists(img_path):
                        with open(img_path, 'rb') as f:
                            while True:
                                chunk = f.read(8192)
                                if not chunk:
                                    break
                                hasher.update(chunk)
        except Exception:
            pass

    return hasher.hexdigest()


def get_last_hash():
    path = 'createamod/.lasthash'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ''


def save_last_hash(hash_value):
    path = 'createamod/.lasthash'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(hash_value)


def main():
    main_config = load_main_config()

    current_hash = compute_input_hash(main_config)
    last_hash = get_last_hash()

    if current_hash == last_hash:
        print("No changes detected in createamod configs. Skipping update.")
        return

    own_blocks, mixin_blocks, own_items, mixin_items, own_entities, mixin_entities = load_blocks(main_config)
    config = {
        'modid': main_config.get('id', 'modid'),
        'group': main_config.get('group', 'com.example'),
        'own_blocks': own_blocks,
        'mixin_blocks': mixin_blocks,
        'own_items': own_items,
        'mixin_items': mixin_items,
        'own_entities': own_entities,
        'mixin_entities': mixin_entities,
    }
    sync_modid(config, main_config)
    sync_group(config)
    clean_generated_resources(config)
    generate_mod_blocks(config)
    generate_mod_items(config)
    generate_entities(config)
    update_example_mod(config)
    generate_blockstates(config)
    generate_models(config)
    generate_lang(config)
    generate_mixins(config)
    generate_item_mixins(config)
    save_last_hash(current_hash)
    print("\nUpdate complete!")


if __name__ == '__main__':
    main()
