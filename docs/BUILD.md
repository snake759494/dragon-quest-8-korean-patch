# 빌드 방법

필요: Python 3.12+, `pip install numpy pillow scipy scikit-image pycdlib`, NanumSquare Neo 글꼴(`NanumSquareNeo-cBd.ttf`, 네이버 배포)

1. 저장소 최상위에 원본 ISO `Dragon Quest VIII - Sora to Umi to Daichi to Norowareshi Himegimi (Japan, Asia).iso`와 `NanumSquareNeo-cBd.ttf`를 둡니다.
2. 원문 추출(대조·검사용, 저장소에는 원문을 싣지 않음):
   ```
   python tools/extract.py      # 이벤트·mes·str
   python tools/btltext.py      # 전투 텍스트·몬스터 이름
   python tools/stbtext.py      # 맵 스크립트 문장
   python tools/menutext.py     # 책·세이브 화면·기타 메뉴
   python tools/elfstr.py       # 실행파일 문자열
   ```
3. 검사: `python tools/check_text.py` (오류 0건이어야 함)
4. 빌드: `python tools/build.py` → 최상위에 `DQ8_KR.iso`
5. 차분: `xdelta3 -e -9 -B 536870912 -s <원본.iso> DQ8_KR.iso DQ8_KO_v1.0.xdelta`

번역 파일 형식과 규칙은 `translation/번역_규칙.md`를 참고하세요.
