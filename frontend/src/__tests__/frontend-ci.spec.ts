import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const workflowPath = resolve(process.cwd(), '../.github/workflows/frontend.yml')

function uncommented(source: string): string {
  return source
    .split('\n')
    .filter((line) => !/^\s*#/.test(line))
    .join('\n')
}

function onBlock(yaml: string): string {
  const lines = yaml.split('\n')
  const start = lines.findIndex((line) => /^on:/u.test(line))
  if (start < 0) return ''
  const first = lines[start] ?? ''
  if (first.includes('[')) return first
  const block = [first]
  for (const line of lines.slice(start + 1)) {
    if (/^[^\s#]/u.test(line)) break
    block.push(line)
  }
  return block.join('\n')
}

describe('GitHub Actions frontend job', () => {
  it('runs on push and pull_request with Node 22, npm ci, type-check, and unit tests', () => {
    expect(existsSync(workflowPath)).toBe(true)

    const yaml = uncommented(readFileSync(workflowPath, 'utf8'))
    const triggers = onBlock(yaml)

    expect(triggers).toMatch(/\bpush\b/)
    expect(triggers).toMatch(/\bpull_request\b/)
    expect(yaml).toMatch(/node-version:\s*['"]?22\b/)
    expect(yaml).toMatch(/working-directory:\s*frontend|\bnpm --prefix frontend\b/)
    expect(yaml).toMatch(/\bnpm ci\b/)
    expect(yaml).toMatch(/npm run type-check/)
    expect(yaml).toMatch(/npm run test:unit -- --run/)
  })
})
