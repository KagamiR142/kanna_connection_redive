/** 与后端 boss_assets.boss_icon_cdn_urls 顺序一致 */
export function bossAvatarPrimary(unitId: number): string {
  return `https://redive.estertion.win/icon/unit/${unitId}.webp`
}

export function bossAvatarFallback(unitId: number): string {
  return `https://wthee.xyz/redive/jp/resource/icon/unit/${unitId}.webp`
}
