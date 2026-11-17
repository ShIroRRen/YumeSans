import { existsSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'

import { fetchFromZip } from './ziprange'

const ROOT = join(import.meta.dir, '..')
const SRC = join(ROOT, '.cache')

const FUSION_URL =
	'https://github.com/SpaceTimee/Fusion-JetBrainsMapleMono/releases/download/1.2304.79/JetBrainsMapleMono-NF-NR-XX-XX.zip'
const UBUNTU_URL = 'https://github.com/canonical/Ubuntu-Sans-fonts/releases/download/v1.006/UbuntuSans-fonts-1.006.zip'
const CHILL_URL = 'https://github.com/Warren2060/ChillRound/releases/download/v3.200/ChillRoundF_v3.200.zip'

type Job = { url: string; match: RegExp; out: string; label: string }

const JOBS: Job[] = [
	{
		url: UBUNTU_URL,
		match: /^UbuntuSans-fonts-1\.006\/ttf\/UbuntuSans-Regular\.ttf$/,
		out: 'UbuntuSans-Regular.ttf',
		label: 'Ubuntu Sans Regular'
	},
	{
		url: CHILL_URL,
		match: /ChillRoundFRegular\.ttf$/,
		out: 'ChillRoundF-Regular.ttf',
		label: 'ChillRoundF Regular'
	},
	{
		url: FUSION_URL,
		match: /JetBrainsMapleMono-Regular\.ttf$/,
		out: 'JetBrainsMapleMono-Regular.ttf',
		label: 'JetBrains Maple Mono NF+NR Regular'
	}
]

async function fetchNotoEmoji() {
	const repo = join(SRC, 'noto-emoji')
	const svgDir = join(repo, 'svg')
	if (existsSync(svgDir)) {
		const num = [...new Bun.Glob('*.svg').scanSync(svgDir)].length
		if (num) {
			console.log(`  skip noto-emoji svg/ (${num} files)`)
			return
		}
	}
	const cmd = async (cmd: string[], cwd?: string) => {
		const proc = Bun.spawn(cmd, { cwd, stdout: 'inherit', stderr: 'inherit' })
		if ((await proc.exited) !== 0) throw new Error(`${cmd.join(' ')} failed`)
	}
	if (!existsSync(repo)) {
		await cmd([
			'git',
			'clone',
			'--filter=blob:none',
			'--no-checkout',
			'--depth=1',
			'https://github.com/googlefonts/noto-emoji',
			repo
		])
	}
	await cmd(['git', 'sparse-checkout', 'init', '--cone'], repo)
	await cmd(['git', 'sparse-checkout', 'set', 'svg'], repo)
	await cmd(['git', 'fetch', '--depth=1', 'origin', '98fe0a9ed427251614f732cb0a80bcfea3733424'], repo)
	await cmd(['git', 'checkout', '98fe0a9ed427251614f732cb0a80bcfea3733424'], repo)
	console.log(`  noto emoji svg: ${[...new Bun.Glob('*.svg').scanSync(svgDir)].length} files`)
}

mkdirSync(SRC, { recursive: true })
for (const job of JOBS) {
	const dest = join(SRC, job.out)
	if (existsSync(dest)) {
		console.log(`  skip ${job.out}`)
		continue
	}
	process.stdout.write(`  GET  ${job.label} ... `)
	const buf = await fetchFromZip(job.url, job.match)
	await Bun.write(dest, buf)
	console.log(`${(buf.length / 1048576).toFixed(2)} MB`)
}

await fetchNotoEmoji()