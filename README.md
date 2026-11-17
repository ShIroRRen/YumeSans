# YumeSans

> [!NOTE]
> 本项目未修改任何字形，仅聚合各字体内容

## 结构

| 包/Font Family                            | 变动                           | 上游                                                                                                        | 授权                                                              |
| ----------------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `@yesans/latin`: **YumeSans Latin**       | 仅改名                         | [Ubuntu Sans](https://github.com/canonical/Ubuntu-Sans-fonts)                                               | [UFL 1.0](licenses/UFL-1.0.txt)                                   |
| `@yesans/cjk`: **YumeSans CJK**           | 去除非 CJK 字形                | [ChillRoundF](https://github.com/Warren2060/ChillRound)                                                     | [OFL 1.1](licenses/OFL-1.1.txt)                                   |
| `@yesans/emoji`: **YumeSans Emoji**       | 1.39 旧版本重编 COLRv1 无旗帜  | [Noto Color Emoji](https://github.com/googlefonts/noto-emoji/tree/98fe0a9ed427251614f732cb0a80bcfea3733424) | [OFL 1.1](licenses/OFL-1.1.txt)                                   |
| `@yesans/mono`: **YumeSans Mono**         | 仅改名                         | [JetBrains Maple Mono](https://github.com/SpaceTimee/Fusion-JetBrainsMapleMono) `NF+NR`                     | [OFL 1.1](licenses/OFL-1.1.txt)                                   |
| `@yesans/sans`: **YumeSans**              | CSS 聚合 (Latin + CJK + Emoji) | —                                                                                                           | [UFL 1.0](licenses/UFL-1.0.txt) + [OFL 1.1](licenses/OFL-1.1.txt) |
| `@yesans/mono-all`: **YumeSans Mono ALL** | 单字体合体 (Mono + Emoji)      | —                                                                                                           | [OFL 1.1](licenses/OFL-1.1.txt)                                   |

> [!NOTE]
> `@yesans/sans` 仅进行了 CSS 聚合在同一 `font-family` 指向多个字体，未将 Ubuntu Sans 与其他 OFL 字体合并
>
> 单字体合并版本仅供本地测试使用

字体按照上游字体按 [UFL 1.0](licenses/UFL-1.0.txt)/[OFL 1.1](licenses/OFL-1.1.txt) 许可分发，项目代码以 [F2DLL](LICENSE.txt) 许可分发

字体仅提供 **Regular**，产物提供 `ttf`、`woff`、切片 `woff2`，CSS 默认拉取 `woff2`