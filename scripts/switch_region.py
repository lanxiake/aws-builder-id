#!/usr/bin/env python3
"""
地区切换工具
快速切换不同地区的环境配置
"""

import yaml
import sys
from pathlib import Path


def switch_region(region: str):
    """切换地区配置"""
    valid_regions = ['germany', 'japan', 'usa']
    
    if region not in valid_regions:
        print(f"❌ 无效的地区: {region}")
        print(f"✅ 可用地区: {', '.join(valid_regions)}")
        return False
    
    config_path = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
    
    # 读取配置
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 更新地区
    old_region = config['region']['current']
    config['region']['current'] = region
    
    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)
    
    print(f"✅ 地区已切换: {old_region} -> {region}")
    
    # 显示当前配置
    profile = config['region']['profiles'][region]
    print(f"\n📍 当前地区配置:")
    print(f"  语言: {profile['locale']}")
    print(f"  时区: {profile['timezone']}")
    print(f"  Accept-Language: {profile['accept_language']}")
    print(f"  User-Agent 数量: {len(profile['user_agents'])}")
    
    return True


def show_current():
    """显示当前地区配置"""
    config_path = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    current = config['region']['current']
    profile = config['region']['profiles'][current]
    
    print(f"📍 当前地区: {current.upper()}")
    print(f"  语言: {profile['locale']}")
    print(f"  时区: {profile['timezone']}")
    print(f"  Accept-Language: {profile['accept_language']}")
    print(f"  代理: {'已启用' if config['region'].get('use_proxy') else '未启用'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  查看当前配置: python switch_region.py show")
        print("  切换地区: python switch_region.py [germany|japan|usa]")
        print()
        show_current()
    elif sys.argv[1] == "show":
        show_current()
    else:
        switch_region(sys.argv[1].lower())
