#!/bin/bash
#SBATCH --job-name=pbit186-bridge-build
#SBATCH --partition=gpu5090
#SBATCH --cpus-per-task=4
#SBATCH --mem=6G
#SBATCH --time=00:15:00
set -euo pipefail
TASK=/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/bridge_build_f070576b
VENDOR=/home/Hongjie_Zeng/projects/pbit-dramsys-20261014/vendor
cmake -S "$TASK/source" -B "$TASK/build" -DCMAKE_BUILD_TYPE=Release -DDRAMSYS_SOURCE="$VENDOR/DRAMSys" -DFETCHCONTENT_SOURCE_DIR_DRAMPOWER="$VENDOR/deps/drampower/DRAMPower-6.3.1" -DFETCHCONTENT_SOURCE_DIR_DRAMUTILS="$VENDOR/deps/dramutils/DRAMUtils-1.16.0" -DFETCHCONTENT_SOURCE_DIR_FMT="$VENDOR/deps/fmt/fmt-12.1.0" -DFETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON="$VENDOR/deps/nlohmann_json/json-3.12.0" -DFETCHCONTENT_SOURCE_DIR_SQLITE3="$VENDOR/deps/sqlite3/sqlite-amalgamation-3470000" -DFETCHCONTENT_SOURCE_DIR_SYSTEMCLANGUAGE="$VENDOR/deps/systemclanguage/systemc-3.0.2"
cmake --build "$TASK/build" --target pbit_dram_bridge_sg_v6_audit -j 4
cd /home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/w8_6b0df70b/source
/usr/bin/python3 -B architecture_tlm/unified_v6/probes/dram_sg_probe.py --bridge "$TASK/build/pbit_dram_bridge_sg_v6_audit" --config architecture_tlm/unified_v6/configs/dramsys/ddr4_2ch_2rank_NoPowerDown_core_limits.json --output "$TASK/probe" --commit f070576b9cde6b710ea1fa19e605d63c294432c2
