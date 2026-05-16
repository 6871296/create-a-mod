#!/bin/bash
# Create a mod Terminal

set -euo pipefail

# 显示帮助
show_help() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cat "$SCRIPT_DIR/help.txt"
}

# 创建新项目
create_new() {
    shift  # 移除 "new" 命令本身
    local mcver=""
    local projName=""
    local i=0
    local args=("$@")

    while [ $i -lt ${#args[@]} ]; do
        local arg="${args[$i]}"
        case "$arg" in
            -mcv|--mc-version)
                i=$((i + 1))
                if [ $i -lt ${#args[@]} ]; then
                    mcver="${args[$i]}"
                else
                    echo "Error: $arg requires a value." >&2
                    exit 1
                fi
                ;;
            -*)
                echo "Warning: Unknown option $arg" >&2
                ;;
            *)
                if [ -z "$projName" ]; then
                    projName="$arg"
                fi
                ;;
        esac
        i=$((i + 1))
    done

    if [ -z "$projName" ]; then
        echo "Error: Project name is required." >&2
        echo 'Usage: createamod new [--mc-version/-mcv <mcVersion>] <projName>' >&2
        exit 1
    fi

    echo "Cloning fabric example mod..."
    if [ -z "$mcver" ]; then
        echo "Minecraft version: latest"
        git clone https://github.com/FabricMC/fabric-example-mod.git "$projName"
    else
        echo "Minecraft version: $mcver"
        git clone -b "$mcver" https://github.com/FabricMC/fabric-example-mod.git "$projName"
    fi

    cd "$projName"
    echo
    echo -e "\033[0;1mInitializing project $projName...\033[0m"

    if [ -f ./gradlew ]; then
        chmod +x ./gradlew
        bash ./gradlew genSources || echo "Warning: genSources failed, you may need to run it manually."
    else
        echo "Warning: gradlew not found."
    fi

    mkdir -p ./createamod/blocks

    # Generate a starter main config
    mkdir -p createamod
    cat > createamod/config.createamod.json << 'EOF'
{
    "id": "modid",
    "name": "Example Mod",
    "version": "1.0.0",
    "description": "",
    "author": "",
    "minecraft-version": "1.20.6",
    "group": "com.example",
    "files": [
        "*.createamod.json"
    ]
}
EOF

    echo
    echo -e "\033[0;1;32mCREATION READY!\033[0m"
    echo 'Edit createamod/config.createamod.json and createamod/blocks/*.createamod.json, then run "createamod update".'
    echo 'See "createamod help" for more info.'
}

update(){
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ ! -f "./createamod/config.createamod.json" ]; then
        echo "Error: createamod/config.createamod.json not found in current directory."
        echo "Make sure you are inside a createamod project directory."
        exit 1
    fi
    echo -e "\033[0;1mUpdating mod from createamod/config.createamod.json...\033[0m"
    python3 "$SCRIPT_DIR/generate.py"
}

runClient(){
    update
    echo -e "\033[0;1mStarting Minecraft client...\033[0m"
    ./gradlew runClient
}

case "${1:-}" in
    "new")
        create_new "$@"
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
	"update")
		update
		;;
	"runClient")
		runClient
		;;
    "")
        echo "createamod: error: No command specified."
        echo 'See "createamod help" for more information.'
        exit 1
        ;;
    *)
        echo "createamod: error: No such command."
        echo 'See "createamod help" for more information.'
        exit 1
        ;;
esac
