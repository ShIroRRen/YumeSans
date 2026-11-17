import { existsSync } from 'node:fs'
import { join } from 'node:path'

import { ensureCnFontSplitNative } from './cnfs'
import { DIST_TTF, FONTS, PKGS, packAggregate, packFont, packMonoALL, type Font } from './pack'

const ROOT = join(import.meta.dir, '..')
const name = process.argv[2] as Font

const TTF_RECIPE = {
	latin: [['python', 'tools/prepare.py', 'latin']],
	cjk: [['python', 'tools/prepare.py', 'cjk']],
	emoji: [['python', 'tools/emoji.py']],
	mono: [['python', 'tools/prepare.py', 'mono']],
	'mono-all': [
		['python', 'tools/prepare.py', 'mono'],
		['python', 'tools/emoji.py'],
		['python', 'tools/combine.py', 'mono-all']
	],
	sans: []
}

const DIST_DEPS = {
	sans: ['latin', 'cjk', 'emoji'],
	'mono-all': ['mono', 'emoji']
}

async function cmd(cmd: string[]) {
	console.log(`$ ${cmd.join(' ')}`)
	const proc = Bun.spawn(cmd, {
		cwd: ROOT,
		stdout: 'inherit',
		stderr: 'inherit',
		env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
	})
	const code = await proc.exited
	if (code !== 0) throw new Error(`${cmd.join(' ')} exited ${code}`)
}

function ttfOf(name: Font): string | undefined {
	return (
		FONTS[name] ??
		(name === 'mono-all' ? { ttf: 'YumeSansMonoALL-Regular.ttf', family: 'Yume Sans Mono', chunk: 0 } : undefined)
	)?.ttf
}

async function ensureTtf(name: Font) {
	const ttf = ttfOf(name)
	if (!ttf) return
	if (existsSync(join(DIST_TTF, ttf))) return
	for (const script of TTF_RECIPE[name] ?? [])
		if (script[0] === 'python' || !existsSync(join(DIST_TTF, ttf))) await cmd(script)
}

async function ensureDist(name: Font) {
	if (existsSync(join(PKGS, name, 'dist', 'index.css'))) return

	if (name === 'sans' || name === 'mono-all') {
		for (const dep of DIST_DEPS[name] ?? []) await ensureDist(dep as Font)
		await ensureTtf(name)
		if (name === 'sans') packAggregate('sans', 'YumeSans', ['latin', 'cjk', 'emoji'])
		else packMonoALL()
		return
	}
	await ensureTtf(name)
	await packFont(name)
}

if (!name || !existsSync(join(PKGS, name, 'package.json'))) process.exit(1)

await ensureCnFontSplitNative()
console.log(`[build:${name}]`)
await ensureDist(name)