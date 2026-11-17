import { join } from 'node:path'

import { packAll } from './pack'

const ROOT = join(import.meta.dir, '..')
const args = process.argv.slice(2)
const onlyFonts = args.includes('--fonts')
const onlyPack = args.includes('--pack')

async function cmd(cmd: string[]) {
	console.log(`\n$ ${cmd.join(' ')}`)
	const proc = Bun.spawn(cmd, {
		cwd: ROOT,
		stdout: 'inherit',
		stderr: 'inherit',
		env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
	})
	const code = await proc.exited
	if (code !== 0) throw new Error(`${cmd.join(' ')} exited ${code}`)
}

if (!onlyPack) {
	await cmd(['python', 'tools/prepare.py', 'all'])
	await cmd(['python', 'tools/emoji.py'])
	await cmd(['python', 'tools/combine.py', 'all'])
}
if (!onlyFonts) await packAll()