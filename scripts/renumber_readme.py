import re
import argparse
import sys

def renumber_headers(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    # H2부터 카운팅 (H1은 문서 제목으로 간주하여 번호 안 붙임)
    # counters[0]은 H2, counters[1]은 H3...
    counters = [0] * 6 
    in_code_block = False
    
    # 기존 번호 패턴 (예: "1. ", "1.2. ", "2.4 ")
    # 헤더 뒤에 오는 숫자+점 패턴을 제거하기 위함
    numbering_pattern = re.compile(r'^#+\s+(\d+(\.\d+)*\.?)\s+')

    for line in lines:
        # 코드 블록 감지 (```)
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            new_lines.append(line)
            continue

        # 코드 블록 안이면 패스
        if in_code_block:
            new_lines.append(line)
            continue

        # 헤더 라인인지 확인
        match = re.match(r'^(#+)\s+(.*)', line)
        if match:
            hashes, content = match.groups()
            level = len(hashes)

            # H1(#)은 번호 매기지 않음 (보통 타이틀)
            if level == 1:
                new_lines.append(line)
                continue
            
            # H2(##)부터 번호 매기기 시작
            # idx 0 -> H2, idx 1 -> H3 ...
            idx = level - 2
            
            if 0 <= idx < len(counters):
                # 현재 레벨 카운트 증가
                counters[idx] += 1
                # 하위 레벨 카운터 초기화
                for i in range(idx + 1, len(counters)):
                    counters[i] = 0
                
                # 번호 문자열 생성 (예: 2.4)
                # 0이 아닌 것만 합침 (H2가 2면 [2,0,0..] -> "2")
                # H3가 2.4면 [2,4,0..] -> "2.4"
                current_numbers = counters[:idx+1]
                number_str = ".".join(map(str, current_numbers))
                
                # 기존에 혹시 있을지 모를 번호 제거
                # 예: "### 2.4 Kiali..." -> "### Kiali..."
                # content 자체가 "2.4 Kiali..." 일 수 있으므로 정규식으로 제거 시도
                # 하지만 이미 line에서 hashes를 뗐으므로 content는 "2.4 Kiali..." 형태임
                
                # content 앞부분의 숫자 패턴 제거
                content_clean = re.sub(r'^(\d+(\.\d+)*\.?)\s+', '', content)
                
                # 새 라인 조합
                new_line = f"{hashes} {number_str}. {content_clean}\n"
                new_lines.append(new_line)
            else:
                # 너무 깊은 레벨(H8 이상)은 그냥 둠
                new_lines.append(line)
        else:
            new_lines.append(line)

    original_content = "".join(lines)
    new_content = "".join(new_lines)

    if original_content != new_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"✅ Renumbered: {file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Markdown file to renumber")
    args = parser.parse_args()
    
    renumber_headers(args.file)
