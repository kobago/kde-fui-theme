# kde-fui-theme

KDE Plasma 6 用の FUI (Futuristic UI) テーマ一式。暗い地 + 1 色の発光 + 細線 + 直角、という文法に Plasma
全体を寄せる。パレット定義 (`build.py` の `PALETTES`) から全ファイルを生成するので、色の変更は 1 箇所で済む。

動作確認: Plasma 6.7.4 / Wayland / Qt 6.11 / CachyOS (2026-09)。

## 中身

| 生成物 | 場所 (インストール後) | 役割 |
|---|---|---|
| 配色 `FUI{Cyan,Amber,Green}.colors` | `~/.local/share/color-schemes/` | Qt / Breeze / GTK ブリッジの色。地 = 濃紺〜黒、文字 = アクセントを白に寄せた色、選択 = accent α0.35 |
| Plasma テーマ `fui-{cyan,amber,green}` | `~/.local/share/plasma/desktoptheme/` | パネル・ポップアップ・ツールチップ・タスク・タブ・入力欄など。全部直角、1px accent_dim 枠、外側に 4 層グロー。ブラー/コントラスト効果は無効 |
| ウィンドウ装飾 `FUI-{Cyan,Amber,Green}` (Aurorae) | `~/.local/share/aurorae/themes/` | 1px accent 枠のみ (グロー・影なし)、タイトルバー 36px、下線 accent_dim。ボタンは線で描いた × □ ─ (閉じる = danger 色) |
| 壁紙 `FUI-{Cyan,Amber,Green}` | `~/.local/share/wallpapers/` | 地色 + 48px/240px グリッド + 走査線。3840×2160 / 2560×1440 |
| グローバルテーマ `org.kobago.fui.{cyan,amber,green}` | `~/.local/share/plasma/look-and-feel/` | 上記 + フォントをまとめて適用する look-and-feel パッケージ |
| Konsole `FUI{Cyan,Amber,Green}.colorscheme` | `~/.local/share/konsole/` | 端末配色 |
| フォント Orbitron / Share Tech Mono / FUI Mono (OFL) | `~/.local/share/fonts/fui/` | ウィンドウタイトル = Orbitron (大文字・字間 +12 %)。UI 本文は既定では**システム標準のまま** (Breeze の Noto Sans / Hack)。`build.py` の `USE_FUI_MONO = True` にすると UI 本文も FUI Mono になる |

UI 本文フォントは当初 FUI Mono にしていたが、既定の英字フォントに戻したいという要望で標準のままにした (`USE_FUI_MONO`)。
`apply.sh` はテーマが値を持たないフォントキーをバックアップの値に戻す (無ければキーを削除して既定に戻す)。

FUI Mono は Share Tech Mono の縦メトリクス (hhea / OS/2 の ascender・descender) を Noto Sans CJK JP に合わせただけの派生
フォント (`build.py` の `make_fui_mono`、fontTools 使用)。元のままだとアセントが 13px 対 17px と差があり、日本語を含む行だけ
ベースラインが 4px 下がる (Dolphin の更新日列で指摘された実例あり)。OFL の Reserved Font Name "Share" のため改名している。
あわせて字送りを 0.54em → 0.60em (Hack / DejaVu Sans Mono と同じ) に広げ、字形はセル中央に寄せてある (「字間が狭くて
読みにくい」と指摘された実例あり)。値は `build.py` の `MONO_ADVANCE_EM`。書体側で広げているので GTK / Chrome / Plasma QML
にも同じ字間が効く。

## 使い方

```sh
./install.sh          # フォント導入 → build.py → ~/.local 以下へコピー (root 不要)
./apply.sh cyan       # 適用。初回に元の設定を ~/.config/kde-fui-theme/backup.ini へ保存
./apply.sh amber      # パレット切替 (cyan / amber / green)
./restore.sh          # 適用前の設定に戻す
```

`apply.sh` が触るもの: 配色、Plasma テーマ、ウィンドウ装飾 (kwinrc)、フォント 6 種 (kdeglobals)、壁紙、
`LookAndFeelPackage`。パネルの配置やウィジェット構成には触らない。
Ghostty 用の同じ配色は [ghostty-fui-theme](https://github.com/kobago/ghostty-fuide-theme) に分けてある。
システム設定 > 外観 > グローバルテーマ から「FUI Cyan」を選んでも同じものが適用できる。

フォントの反映は `org.kde.KDEPlatformTheme.refreshFonts` の D-Bus シグナルで既存プロセスにも通知する
(これが無いと KWin のタイトルフォントが更新されない)。

## パレット (`build.py` / fui スキル `tokens.md` と同じ値)

| token | CYAN | AMBER | GREEN |
|---|---|---|---|
| accent | `#00E5FF` | `#FFB020` | `#46FF8C` |
| accent_dim | `#00788C` | `#8C6010` | `#1E8246` |
| warn / danger / ok | `#FFAA28` / `#FF465A` / `#50FFA0` | `#00E5FF` / `#FF465A` / `#50FFA0` | `#FFAA28` / `#FF465A` / `#00E5FF` |
| text / text_dim | `#AAE6F0` / `#5A8C9B` | `#F0DCB4` / `#96825A` | `#B4F0C8` / `#5A966E` |
| bg_deep / bg_panel | `#060C12` / `#0A1620` (α .92 / .78) | `#120C04` / `#1E1608` | `#041008` / `#081C0E` |

KDE の色ロールへの対応: Window = bg_panel、View/Header/Tooltip = bg_deep、Button = accent_dim α0.28、
Selection = accent α0.35、DecorationFocus/Hover = accent、Negative/Neutral/Positive = danger/warn/ok。

## ライセンス

- スクリプトと生成されるテーマ一式: GPL-2.0-or-later (`LICENSE`)。壁紙は CC0。
- 同梱フォント (Orbitron / Share Tech Mono): SIL Open Font License 1.1。詳細は `fonts/README.md`。
- 派生フォント FUI Mono は `dist/` に生成されるだけでリポジトリには含めない (OFL、名称変更済み)。

## 設計メモ・制約

- 角は全て直角、角丸 0。チャンファーは入れていない。
- Plasma のパネル・ポップアップは影を使わず、accent の 4 層 (α .10/.05/.033/.025) をブラー無しで外側に重ねている
  (`shadow-*` 要素)。ウィンドウ装飾は当初同じグローを Aurorae の padding 領域に置いていたが、窓の周りに光る帯が出るのは
  好まれなかったので `PAD = 0` にして 1px の線だけにしてある (padding 領域に地色を塗ると黒い影に見える点にも注意)。
- Aurorae の枠幅は rc の `BorderLeft=1` ではなく KWin の「枠の太さ」設定で決まる (標準 = 4px)。線より内側は
  装飾の中央要素で埋められるため、中央要素も地色 (bg_deep α.92) で塗ってある。透明にすると線と中身の間に
  背後の窓が透ける帯ができる (実例あり)。
- ウィジェットスタイルは Breeze のまま (Kvantum 不使用)。そのため Qt アプリ内のボタンや入力欄の角丸 (約 3px) は残る。
  完全な直角が要るなら Kvantum + 自作 kvconfig が必要。
- 端末の 16 色は ANSI の意味を保つため、blue / magenta スロットだけパレット外の鈍い色を当てている。
- 生成物 `dist/` は `install.sh` が毎回作り直す。PNG 生成に `rsvg-convert` (librsvg) が要る。
