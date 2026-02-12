#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenIDCS 多语言翻译生成器
使用 Google Translate API 自动生成多语言翻译文件
"""

import re
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Tuple
from deep_translator import GoogleTranslator
from tqdm import tqdm

# 支持的语言映射 (文件名后缀 -> Google Translate 语言代码)
LANGUAGE_MAP = {
    'ar-ar': 'ar',  # 阿拉伯语
    'bn-bd': 'bn',  # 孟加拉语
    'de-de': 'de',  # 德语
    'en-us': 'en',  # 英语
    'es-es': 'es',  # 西班牙语
    'fr-fr': 'fr',  # 法语
    'hi-in': 'hi',  # 印地语
    'it-it': 'it',  # 意大利语
    'ja-jp': 'ja',  # 日语
    'ko-kr': 'ko',  # 韩语
    'pt-br': 'pt',  # 葡萄牙语
    'ru-ru': 'ru',  # 俄语
    'ur-pk': 'ur',  # 乌尔都语
    'zh-tw': 'zh-TW',  # 繁体中文
}

# 语言全称映射
LANGUAGE_NAMES = {
    'ar-ar': 'Arabic',
    'bn-bd': 'Bengali',
    'de-de': 'German',
    'en-us': 'English',
    'es-es': 'Spanish',
    'fr-fr': 'French',
    'hi-in': 'Hindi',
    'it-it': 'Italian',
    'ja-jp': 'Japanese',
    'ko-kr': 'Korean',
    'pt-br': 'Portuguese',
    'ru-ru': 'Russian',
    'ur-pk': 'Urdu',
    'zh-tw': 'Traditional Chinese',
}


class POFileTranslator:
    """PO文件翻译器"""
    
    def __init__(self, source_file: str):
        """
        初始化翻译器
        
        Args:
            source_file: 源PO文件路径 (zh-cn.po)
        """
        self.source_file = source_file
        self.entries: List[Tuple[str, str]] = []
        
    def parse_po_file(self) -> bool:
        """
        解析PO文件，提取msgid和msgstr对
        
        Returns:
            是否解析成功
        """
        try:
            with open(self.source_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用正则表达式提取 msgid 和 msgstr
            pattern = r'msgid\s+"([^"]*)"\s+msgstr\s+"([^"]*)"'
            matches = re.findall(pattern, content)
            
            # 过滤掉空的msgid（文件头）
            self.entries = [(msgid, msgstr) for msgid, msgstr in matches if msgid]
            
            print(f"✓ 成功解析 {len(self.entries)} 条翻译条目")
            return True
            
        except Exception as e:
            print(f"✗ 解析PO文件失败: {e}")
            return False
    
    def translate_text(self, text: str, target_lang: str, retry_count: int = 3) -> str:
        """
        翻译文本（带重试机制）
        
        Args:
            text: 要翻译的文本
            target_lang: 目标语言代码
            retry_count: 重试次数
            
        Returns:
            翻译后的文本
        """
        for attempt in range(retry_count):
            try:
                translator = GoogleTranslator(source='zh-CN', target=target_lang)
                result = translator.translate(text)
                return result
                
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(1)  # 等待1秒后重试
                    continue
                else:
                    tqdm.write(f"  ⚠ 翻译失败 '{text[:30]}...' -> {target_lang}: {e}")
                    return text  # 翻译失败时返回原文
    
    def generate_po_file(self, target_lang_code: str, output_file: str) -> bool:
        """
        生成目标语言的PO文件
        
        Args:
            target_lang_code: 目标语言代码 (如 'en', 'ja')
            output_file: 输出文件路径
            
        Returns:
            是否生成成功
        """
        try:
            # 获取语言名称
            lang_key = os.path.basename(output_file).replace('.po', '')
            lang_name = LANGUAGE_NAMES.get(lang_key, target_lang_code.upper())
            
            # 生成文件头
            header = f"""# OpenIDCS {lang_name} Translation File
# Copyright (C) 2024 OpenIDCS Team
# This file is distributed under the same license as the OpenIDCS package.
#
msgid ""
msgstr ""
"Project-Id-Version: OpenIDCS 1.0\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\\n"
"PO-Revision-Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\\n"
"Last-Translator: Auto Generated\\n"
"Language-Team: {lang_name}\\n"
"Language: {target_lang_code}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"

"""
            
            # 翻译所有条目
            translated_entries = []
            total = len(self.entries)
            
            print(f"\n开始翻译到 {lang_name} ({target_lang_code})...")
            
            # 使用tqdm显示进度条
            with tqdm(total=total, desc=f"翻译进度", unit="条", 
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
                
                for msgid, msgstr in self.entries:
                    # 翻译msgstr（中文）到目标语言
                    translated = self.translate_text(msgstr, target_lang_code)
                    translated_entries.append((msgid, translated))
                    
                    # 更新进度条
                    pbar.update(1)
                    pbar.set_postfix({'当前': msgstr[:20] + '...' if len(msgstr) > 20 else msgstr})
            
            # 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(header)
                
                for msgid, msgstr in translated_entries:
                    f.write(f'msgid "{msgid}"\n')
                    f.write(f'msgstr "{msgstr}"\n\n')
            
            print(f"✓ 成功生成: {output_file}")
            return True
            
        except Exception as e:
            print(f"✗ 生成PO文件失败: {e}")
            return False
    
    def generate_all_languages(self, output_dir: str = None) -> Dict[str, bool]:
        """
        生成所有语言的翻译文件
        
        Args:
            output_dir: 输出目录，默认为源文件所在目录
            
        Returns:
            各语言生成结果字典
        """
        if output_dir is None:
            output_dir = os.path.dirname(self.source_file)
        
        results = {}
        
        for lang_suffix, lang_code in LANGUAGE_MAP.items():
            output_file = os.path.join(output_dir, f"{lang_suffix}.po")
            success = self.generate_po_file(lang_code, output_file)
            results[lang_suffix] = success
        
        return results


def main():
    """主函数"""
    print("=" * 60)
    print("OpenIDCS 多语言翻译生成器")
    print("=" * 60)
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_file = os.path.join(script_dir, 'zh-cn.po')
    
    # 检查源文件是否存在
    if not os.path.exists(source_file):
        print(f"✗ 错误: 找不到源文件 {source_file}")
        sys.exit(1)
    
    print(f"\n源文件: {source_file}")
    
    # 创建翻译器
    translator = POFileTranslator(source_file)
    
    # 解析源文件
    if not translator.parse_po_file():
        sys.exit(1)
    
    # 询问用户要生成哪些语言
    print("\n可用语言:")
    for idx, (suffix, name) in enumerate(LANGUAGE_NAMES.items(), 1):
        print(f"  {idx:2d}. {suffix:8s} - {name}")
    
    print("\n选项:")
    print("  - 输入语言编号（用逗号分隔，如: 1,3,5）")
    print("  - 输入 'all' 生成所有语言")
    print("  - 输入 'q' 退出")
    
    choice = input("\n请选择: ").strip().lower()
    
    if choice == 'q':
        print("已取消")
        sys.exit(0)
    
    # 确定要生成的语言
    if choice == 'all':
        selected_langs = list(LANGUAGE_MAP.keys())
    else:
        try:
            indices = [int(x.strip()) for x in choice.split(',')]
            lang_list = list(LANGUAGE_MAP.keys())
            selected_langs = [lang_list[i-1] for i in indices if 1 <= i <= len(lang_list)]
        except Exception as e:
            print(f"✗ 无效的输入: {e}")
            sys.exit(1)
    
    if not selected_langs:
        print("✗ 未选择任何语言")
        sys.exit(1)
    
    print(f"\n将生成 {len(selected_langs)} 个语言版本")
    
    # 生成翻译文件
    success_count = 0
    print(f"\n{'='*60}")
    print(f"开始批量翻译 {len(selected_langs)} 个语言")
    print(f"{'='*60}")
    
    for idx, lang_suffix in enumerate(selected_langs, 1):
        lang_code = LANGUAGE_MAP[lang_suffix]
        lang_name = LANGUAGE_NAMES[lang_suffix]
        output_file = os.path.join(script_dir, f"{lang_suffix}.po")
        
        print(f"\n[{idx}/{len(selected_langs)}] {lang_name} ({lang_suffix})")
        print("-" * 60)
        
        if translator.generate_po_file(lang_code, output_file):
            success_count += 1
            print(f"✓ 完成")
        else:
            print(f"✗ 失败")
    
    # 显示结果
    print("\n" + "=" * 60)
    print(f"完成! 成功生成 {success_count}/{len(selected_langs)} 个翻译文件")
    print("=" * 60)


if __name__ == '__main__':
    main()
