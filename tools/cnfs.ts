import { join } from 'node:path'

const ROOT = join(import.meta.dir, '..')

function scan(pattern: string): boolean {
	try {
		for (const _ of new Bun.Glob(pattern).scanSync({ cwd: ROOT })) return true
	} catch {}
	return false
}

export async function ensureCnFontSplitNative() {
	const patterns = [
		'node_modules/.bun/**/node_modules/cn-font-split/dist/libffi-*',
		'node_modules/cn-font-split/dist/libffi-*'
	]
	if (patterns.some(scan)) return

	const proc = Bun.spawn(['bunx', 'cn-font-split', 'i', 'default'], {
		cwd: ROOT,
		stdout: 'inherit',
		stderr: 'inherit'
	})
	if ((await proc.exited) !== 0) throw new Error('install cn-font-split failed')
}