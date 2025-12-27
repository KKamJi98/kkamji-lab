#!/bin/bash
# scripts/format-study-readme.sh
# 통합 마크다운 포맷터: H2 구분선 추가 및 헤더 넘버링 자동 갱신

TARGET_DIR="study"
H2_FIXER="tools/markdown-fmt/markdown-formatter/fix_md_h2_rules.py"
RENUMBERER="tools/markdown-fmt/renumber_readme.py"

# 필수 파일 존재 확인
if [ ! -f "$H2_FIXER" ]; then
    echo "❌ Error: $H2_FIXER not found (Symbolic link check failed)"
    exit 1
fi

if [ ! -f "$RENUMBERER" ]; then
    echo "❌ Error: $RENUMBERER not found"
    exit 1
fi

echo "🚀 Starting Markdown Formatting for '$TARGET_DIR'..."

# study 디렉터리 하위의 모든 README.md 파일을 찾아서 처리
find "$TARGET_DIR" -type f -name "README.md" | while read -r file; do
    echo "------------------------------------------"
    echo "Processing: $file"
    
    # 1. H2 스타일 교정 (구분선 추가 등)
    # --no-backup: git 관리를 하므로 백업 파일 생성 안 함
    python3 "$H2_FIXER" --file "$file" --no-backup --verbose
    
    # 2. 헤더 넘버링 자동 갱신
    python3 "$RENUMBERER" --file "$file"
done

echo "------------------------------------------"
echo "✨ All README.md files in '$TARGET_DIR' have been formatted and renumbered!"
