import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import { fontSplit } from 'cn-font-split'
import ttf2woff from 'ttf2woff'

import { ensureCnFontSplitNative } from './cnfs'

export const ROOT = join(import.meta.dir, '..')
export const DIST_TTF = join(ROOT, 'dist', 'ttf')
export const PKGS = join(ROOT, 'pkgs')
const BUILD = join(ROOT, 'build', 'split')

export type Font = 'latin' | 'cjk' | 'emoji' | 'mono' | 'sans' | 'mono-all'

export const FONTS = {
	latin: { ttf: 'YumeSansLatin-Regular.ttf', family: 'YumeSans Latin' },
	cjk: { ttf: 'YumeSansCJK-Regular.ttf', family: 'YumeSans CJK' },
	emoji: { ttf: 'YumeSansEmoji-Regular.ttf', family: 'YumeSans Emoji' },
	mono: { ttf: 'YumeSansMono-Regular.ttf', family: 'YumeSans Mono' }
} as Record<Font, { ttf: string; family: string }>

function faces(css: string): string[] {
	return css.match(/@font-face\{[^}]*\}/g) ?? []
}

function rewriteUrl(css: string, prefix: string): string {
	return css.replace(/url\("\.\/([^"]+\.woff2)"\)/g, `url("${prefix}$1")`).replace(/local\("[^"]*"\),?/g, '')
}

function writeWoff(ttfPath: string, woffPath: string) {
	writeFileSync(woffPath, Buffer.from(ttf2woff(new Uint8Array(readFileSync(ttfPath)))))
}

export async function packFont(name: Font) {
	const spec = FONTS[name]
	if (!spec) throw new Error(`unknown font package: ${name}`)
	const ttfPath = join(DIST_TTF, spec.ttf)
	if (!existsSync(ttfPath)) throw new Error(`${ttfPath} not found`)

	const out = join(PKGS, name, 'dist')
	rmSync(out, { recursive: true, force: true })
	mkdirSync(join(out, 'woff2'), { recursive: true })

	const tmp = join(BUILD, name)
	rmSync(tmp, { recursive: true, force: true })
	await fontSplit({
		input: new Uint8Array(readFileSync(ttfPath)),
		outDir: tmp,
		css: {
			fontFamily: spec.family,
			commentUnicodes: true
		},
		languageAreas: true,
		autoSubset: true,
		fontFeature: true,
		reduceMins: true,
		chunkSize: 520000,
		renameOutputFont: `yumesans.${name}.[index].[ext]`
	})

	let chunks = 0
	for (const file of readdirSync(tmp))
		if (file.endsWith('.woff2')) {
			cpSync(join(tmp, file), join(out, 'woff2', file))
			chunks++
		}

	const cssPath = join(out, 'index.css')
	writeFileSync(cssPath, rewriteUrl(readFileSync(join(tmp, 'result.css'), 'utf8'), 'woff2/'), 'utf8')

	cpSync(ttfPath, join(out, spec.ttf))
	writeWoff(ttfPath, join(out, spec.ttf.replace(/\.ttf$/, '.woff')))

	console.log(`  ${name.padEnd(9)}  chunks: ${chunks}, faces: ${faces(readFileSync(cssPath, 'utf8')).length}`)
}

function parseRange(face: string): Set<number> {
	const m = face.match(/unicode-range:([^;}]+)/)
	const out = new Set<number>()
	if (!m) return out
	for (const part of m[1].split(',')) {
		const seg = part.trim()
		if (!seg.startsWith('U+')) continue
		const [a, b] = seg.slice(2).split('-')
		const lo = Number.parseInt(a, 16)
		const hi = b ? Number.parseInt(b, 16) : lo
		for (let cp = lo; cp <= hi; cp++) out.add(cp)
	}
	return out
}

function formatRange(cps: Set<number>): string {
	const list = [...cps].sort((x, y) => x - y)
	const parts: string[] = []
	let start = list[0]
	let prev = list[0]
	for (const cp of list.slice(1)) {
		if (cp === prev + 1) {
			prev = cp
			continue
		}
		parts.push(start === prev ? `U+${start.toString(16).toUpperCase()}` : `U+${start.toString(16).toUpperCase()}-${prev.toString(16).toUpperCase()}`)
		start = prev = cp
	}
	if (start !== undefined)
		parts.push(start === prev ? `U+${start.toString(16).toUpperCase()}` : `U+${start.toString(16).toUpperCase()}-${prev.toString(16).toUpperCase()}`)
	return parts.join(',')
}

export function packAggregate(name: string, family: string, parts: string[]) {
	const out = join(PKGS, name, 'dist')
	mkdirSync(out, { recursive: true })

	const blocks: string[] = []
	const covered = new Set<number>()

	for (const part of parts) {
		const cssPath = join(PKGS, part, 'dist', 'index.css')
		if (!existsSync(cssPath)) throw new Error(`${cssPath} not found`)
		for (const face of faces(readFileSync(cssPath, 'utf8'))) {
			const cps = parseRange(face)
			const keep = new Set([...cps].filter((cp) => !covered.has(cp)))
			if (keep.size === 0) continue
			for (const cp of keep) covered.add(cp)
			blocks.push(
				face
					.replace(/url\("woff2\//g, `url("../../${part}/dist/woff2/`)
					.replace(/font-family:"[^"]*"/g, `font-family:"${family}"`)
					.replace(/unicode-range:[^;}]+/, `unicode-range:${formatRange(keep)}`)
			)
		}
	}

	writeFileSync(join(out, 'index.css'), blocks.join('\n'), 'utf8')
	console.log(`  ${name.padEnd(9)}  faces: ${blocks.length}`)
}

export function packMonoALL() {
	const ttf = 'YumeSansMonoALL-Regular.ttf'
	const src = join(DIST_TTF, ttf)
	if (!existsSync(src)) throw new Error(`${src} not found`)
	const out = join(PKGS, 'mono-all', 'dist')
	mkdirSync(out, { recursive: true })
	cpSync(src, join(out, ttf))
	writeWoff(src, join(out, ttf.replace(/\.ttf$/, '.woff')))
	packAggregate('mono-all', 'YumeSans Mono ALL', ['mono', 'emoji'])
}

export async function packAll() {
	await ensureCnFontSplitNative()
	mkdirSync(BUILD, { recursive: true })
	for (const name of Object.keys(FONTS)) await packFont(name as Font)
	packAggregate('sans', 'YumeSans', ['latin', 'cjk', 'emoji'])
	packMonoALL()
}

if (import.meta.main) await packAll()