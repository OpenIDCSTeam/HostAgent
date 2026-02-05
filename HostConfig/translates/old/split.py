#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文词语拆分脚本
将PO文件中的句子按中文词语拆分成独立的条目
"""

import re
import sys

# 尝试导入jieba分词库
try:
    import jieba
    import jieba.posseg as pseg
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

# 自定义词典：保护这些短语不被切分
CUSTOM_WORDS = [
    # 系统术语
    '虚拟机', '主机', '控制器', '管理员', '用户名', '密码', 'Token',
    '域名', 'IP地址', 'NAT端口', 'Web代理', 'CPU核心', 'GPU显存',
    'SSH代理', 'VNC控制台', 'ISO镜像', '数据盘', 'VM状态', 'VM',
    
    # 操作术语
    '修改前', '修改后', '修改密码', '修改邮箱', '重置密码', '找回密码',
    '请核对', '请输入', '请点击', '请填写', '请选择',
    '操作成功', '操作失败',
    # 注意：不包含"无法修改"，应该拆分为"无法"和"修改"
    
    '创建成功', '创建失败', '删除成功', '删除失败',
    '保存成功', '保存失败', '加载成功', '加载失败',
    '启动成功', '启动失败', '停止成功', '停止失败',
    
    # 状态术语
    '运行中', '已启用', '已禁用', '已删除', '已创建',
    '已加载', '已保存', '已停止', '已验证', '未验证',
    
    # 常见短语
    '如果您', '如果没有', '请输入', '请点击', '系统设置', '系统配置',
    '端口转发', '邮箱地址', '访问Token', '资源配额',
    '网络配置', '网卡配置', '磁盘管理', '备份管理',
    '配置信息', '配置文件', '配置错误',
    
    # 组合词
    '添加主机', '删除主机', '更新主机', '扫描虚拟机',
    '创建虚拟机', '删除虚拟机', '编辑虚拟机', '重装系统',
    '挂载ISO', '卸载ISO', '挂载数据盘', '卸载数据盘',
    '添加代理', '删除代理', '更新代理', '添加规则', '删除规则',
    '邮件服务', '测试邮件', '验证邮件', '发送邮件',
    '个人设置', '系统设置', '权限信息', '账户状态',
    '配额不足', '配额充足', '已使用', '当前',
    
    # 动词+名词
    '执行任务', '定时任务', '初始执行', '开始清理',
    '开始备份', '开始恢复', '已完成', '正在加载', '正在处理',
    
    # 短语
    '硬盘大小', '内存大小', '显存大小', '磁盘大小',
    '虚拟机详情', '主机详情', '系统信息',
    '网络检查', '网络配置',
]

# 合并规则：将相邻的词合并成更长的短语
MERGE_RULES = [
    # 动词+结果（成功/失败）
    (r'^(修改创建删除添加更新保存加载启动停止)$', r'^(成功失败)$'),  # 修改+成功，删除+失败等
    
    # 注意：不合并"无法+修改"，保持分开
    # 注意：不合并"修改+成功"，保持分开（用户期望）
]

def init_jieba():
    """
    初始化jieba，添加自定义词典
    """
    if not HAS_JIEBA:
        return
    
    # 添加自定义词，设置高权重
    for word in CUSTOM_WORDS:
        jieba.add_word(word, freq=1000, tag='nw')
    
    # 添加常见的英文技术术语
    tech_terms = [
        'VM', 'Token', 'IP', 'MAC', 'DNS', 'SSH', 'VNC', 'ISO',
        'CPU', 'GPU', 'RAM', 'HDD', 'SSD', 'LAN', 'WAN', 'NAT',
        'API', 'URL', 'PID', 'UID', 'MB', 'GB', 'TB', 'Mbps',
        'VMX', 'VMID', 'LXD', 'Docker', 'Hyper-V', 'Proxmox',
        'ESXi', 'vSphere', 'Workstation', 'Flask', 'Resend',
    ]
    for term in tech_terms:
        jieba.add_word(term, freq=2000, tag='eng')

def parse_po_file(file_path):
    """
    解析PO文件
    返回：header字符串, 条目列表
    """
    # 先读取所有行
    with open(file_path, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()
    
    # 找到第一个非空msgid的行号
    first_entry_index = 0
    for i, line in enumerate(all_lines):
        if line.startswith('msgid '):
            msgid_content = line[7:].strip().strip('"')
            if msgid_content:  # 非空的msgid
                first_entry_index = i
                break
    
    # 分离头部和条目
    header_lines = all_lines[:first_entry_index]
    entry_lines = all_lines[first_entry_index:]
    
    # 解析条目
    entries = []
    current_msgid = None
    current_msgstr = None
    current_comment = []
    
    for i, line in enumerate(entry_lines):
        if line.startswith('#'):
            # 保存之前的条目（如果有）
            if current_msgid is not None:
                entries.append({
                    'comment': current_comment,
                    'msgid': current_msgid,
                    'msgstr': current_msgstr
                })
                current_msgid = None
                current_msgstr = None
                current_comment = []
            current_comment.append(line)
        elif line.startswith('msgid '):
            # 保存之前的条目（如果有）
            if current_msgid is not None:
                entries.append({
                    'comment': current_comment,
                    'msgid': current_msgid,
                    'msgstr': current_msgstr
                })
                current_msgid = None
                current_msgstr = None
                current_comment = []
            current_msgid = line[7:].strip().strip('"')
        elif line.startswith('msgstr '):
            current_msgstr = line[8:].strip().strip('"')
        elif line.startswith('"') and current_msgid is not None:
            # 多行字符串
            content = line.strip().strip('"')
            if current_msgstr is None:
                current_msgid += content
            else:
                current_msgstr += content
    
    # 保存最后一个条目
    if current_msgid is not None:
        entries.append({
            'comment': current_comment,
            'msgid': current_msgid,
            'msgstr': current_msgstr
        })
    
    return ''.join(header_lines), entries

def merge_adjacent_words(words):
    """
    合并相邻的词语，应用合并规则
    """
    if len(words) <= 1:
        return words
    
    result = words.copy()
    changed = True
    
    while changed:
        changed = False
        new_result = []
        i = 0
        
        while i < len(result):
            if i + 1 < len(result):
                word1 = result[i]
                word2 = result[i + 1]
                
                # 检查是否可以合并
                merged = None
                for rule in MERGE_RULES:
                    pattern1, pattern2 = rule
                    if re.match(pattern1, word1) and re.match(pattern2, word2):
                        merged = word1 + word2
                        break
                
                if merged:
                    new_result.append(merged)
                    i += 2
                    changed = True
                else:
                    new_result.append(word1)
                    i += 1
            else:
                new_result.append(result[i])
                i += 1
        
        result = new_result
    
    return result

def write_po_file(file_path, header, entries):
    """
    写入PO文件
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        # 写入头部
        f.write(header)
        
        # 写入条目
        for entry in entries:
            # 写入注释（如果有）
            for comment in entry.get('comment', []):
                f.write(comment)
            
            # 写入msgid
            f.write(f'msgid "{entry["msgid"]}"\n')
            
            # 写入msgstr
            f.write(f'msgstr "{entry["msgstr"]}"\n')
            
            f.write('\n')

def detect_language(text):
    """
    检测文本语言
    返回: 'zh' (中文), 'en' (英语), 'fr' (法语), or 'other'
    """
    # 统计中文字符
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 统计英文字母
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    
    if chinese_chars > 0:
        return 'zh'
    elif english_chars > 0:
        # 简单区分英语和法语：法语中常出现的字符
        french_chars = len(re.findall(r'[àâäéèêëïîôùûüÿç]', text, re.IGNORECASE))
        if french_chars > english_chars * 0.1:  # 如果法语字符超过10%，认为是法语
            return 'fr'
        else:
            return 'en'
    return 'other'

def tokenize_text(text, language='zh'):
    """
    对文本进行分词
    language: 'zh' (中文), 'en' (英语), 'fr' (法语)
    """
    if language == 'zh':
        return tokenize_chinese(text)
    elif language == 'en':
        return tokenize_english(text)
    elif language == 'fr':
        return tokenize_french(text)
    else:
        return tokenize_simple(text)

def tokenize_chinese(text):
    """
    中文分词
    """
    if not HAS_JIEBA:
        return simple_tokenize(text)
    
    words = list(jieba.cut(text, cut_all=False))
    result = []
    i = 0
    while i < len(words):
        word = words[i]
        if not word.strip():
            i += 1
            continue
        if len(word) == 1 and word in '的、了和与或但而因故然否则可能无法应该必须':
            if result:
                result[-1] = result[-1] + word
            i += 1
            continue
        result.append(word)
        i += 1
    result = merge_adjacent_words(result)
    return result

def tokenize_english(text):
    """
    英语分词：按空格、标点符号拆分
    """
    result = []
    # 匹配：单词/数字/标点
    pattern = r'[a-zA-Z0-9_\-\.\'\']+|[^a-zA-Z0-9_\-\.\'\']'
    
    for match in re.finditer(pattern, text):
        word = match.group().strip()
        if word:
            result.append(word)
    
    return result

def tokenize_french(text):
    """
    法语分词：按空格、标点符号拆分（考虑法语特殊字符）
    """
    result = []
    # 匹配：单词/数字/标点（包含法语特殊字符）
    pattern = r'[a-zA-Zàâäéèêëïîôùûüÿç0-9_\-\'\']+|[^a-zA-Zàâäéèêëïîôùûüÿç0-9_\-\'\']+'
    
    for match in re.finditer(pattern, text):
        word = match.group().strip()
        if word:
            result.append(word)
    
    return result

def tokenize_simple(text):
    """
    通用简单分词
    """
    result = []
    pattern = r'\w+|[^\w\s]'
    for match in re.finditer(pattern, text):
        word = match.group().strip()
        if word:
            result.append(word)
    return result

def split_entry(entry):
    """
    拆分一个条目
    """
    msgid = entry['msgid']
    msgstr = entry['msgstr']
    comment = entry['comment']
    
    if not msgid.strip():
        return [entry]
    
    # 检测语言
    language = detect_language(msgid)
    
    # 对msgid和msgstr进行分词
    msgid_words = tokenize_text(msgid, language)
    msgstr_words = tokenize_text(msgstr, language)
    
    if len(msgid_words) <= 1:
        return [entry]
    
    # 过滤掉只包含标点符号的词
    def filter_words(words):
        filtered = []
        for word in words:
            if word.strip() and re.search(r'\w', word):
                filtered.append(word)
        return filtered
    
    msgid_words = filter_words(msgid_words)
    msgstr_words = filter_words(msgstr_words)
    
    if len(msgid_words) == 0:
        return [entry]
    
    min_len = min(len(msgid_words), len(msgstr_words))
    msgid_words = msgid_words[:min_len]
    msgstr_words = msgstr_words[:min_len]
    
    new_entries = []
    for i, (mid, mstr) in enumerate(zip(msgid_words, msgstr_words)):
        new_entries.append({
            'comment': comment.copy() if i == 0 else [],
            'msgid': mid,
            'msgstr': mstr
        })
    
    return new_entries

def main():
    """
    主函数
    """
    # 解析命令行参数
    if len(sys.argv) < 2:
        print("用法: python split.py <输入文件路径>")
        print("示例: python split.py zh-cn.po")
        print("      python split.py en-us.po")
        print("      python split.py fr-fr.po")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # 检查文件是否存在
    if not input_file.endswith('.po'):
        print("错误: 输入文件必须是 .po 格式")
        sys.exit(1)
    
    # 生成输出文件名
    base_name = input_file.rsplit('.', 1)[0]
    output_file = f"{base_name}_split.po"
    
    # 初始化jieba（仅用于中文）
    if HAS_JIEBA:
        print("初始化jieba分词库...")
        init_jieba()
        print("jieba初始化完成")
    else:
        print("注意: 未安装jieba库，将使用简单分词策略")
    
    print(f"\n正在读取文件: {input_file}")
    header, entries = parse_po_file(input_file)
    print(f"共读取 {len(entries)} 个条目")
    
    # 检测文件语言（基于翻译文本msgstr）
    sample_texts = []
    for entry in entries[:20]:
        if entry['msgstr'] and entry['msgstr'].strip():
            sample_texts.append(entry['msgstr'])
    
    if sample_texts:
        sample_text = ' '.join(sample_texts)
        file_language = detect_language(sample_text)
    else:
        # 如果没有翻译文本，使用msgid
        sample_text = ' '.join([e['msgid'] for e in entries[:10]])
        file_language = detect_language(sample_text)
    
    lang_names = {
        'zh': '中文',
        'en': '英语',
        'fr': '法语',
        'other': '其他'
    }
    print(f"检测到的翻译语言: {lang_names.get(file_language, file_language)}")
    
    print(f"\n开始拆分词语...")
    all_new_entries = []
    
    for i, entry in enumerate(entries, 1):
        if not entry['msgid'].strip():
            all_new_entries.append(entry)
            continue
        
        new_entries = split_entry(entry)
        all_new_entries.extend(new_entries)
        
        if i % 50 == 0:
            print(f"已处理 {i}/{len(entries)} 个条目")
    
    print(f"拆分完成！原 {len(entries)} 个条目 → 新 {len(all_new_entries)} 个条目")
    
    print(f"\n正在写入文件: {output_file}")
    write_po_file(output_file, header, all_new_entries)
    
    print(f"\n完成！输出文件: {output_file}")
    print(f"统计信息:")
    print(f"  - 原始条目数: {len(entries)}")
    print(f"  - 拆分后条目数: {len(all_new_entries)}")
    print(f"  - 增长率: {((len(all_new_entries) - len(entries)) / len(entries) * 100):.1f}%")

if __name__ == '__main__':
    main()