#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'child_process';

/**
 * Detect authentication method from codebase
 * Analyzes code for common auth patterns
 */
function detectAuthMethod(repoRoot) {
  const authPatterns = {
    'magic-link': [
      'magic.link',
      'magicLink',
      'magic-link',
      'magic link',
      'sendMagicLink',
      'verifyMagicLink'
    ],
    'oauth': [
      'oauth',
      'OAuth',
      'googleAuth',
      'githubAuth',
      'supabase.auth',
      'next-auth',
      'auth0'
    ],
    'session': [
      'session',
      'cookie',
      'JWT',
      'jwt',
      'token'
    ],
    'password': [
      'password',
      'username',
      'login',
      'signIn'
    ]
  };

  const results = {
    method: 'unknown',
    confidence: 'low',
    helpers: [],
    files: []
  };

  // Search for auth patterns in codebase
  const searchPaths = [
    path.join(repoRoot, 'src'),
    path.join(repoRoot, 'app'),
    path.join(repoRoot, 'pages'),
    path.join(repoRoot, 'lib'),
    path.join(repoRoot, 'utils'),
    path.join(repoRoot, 'services'),
    path.join(repoRoot, 'auth')
  ].filter(p => fs.existsSync(p));

  const foundPatterns = {};

  for (const [method, patterns] of Object.entries(authPatterns)) {
    foundPatterns[method] = 0;
    
    for (const pattern of patterns) {
      try {
        const command = `grep -r "${pattern}" ${searchPaths.join(' ')} --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" 2>/dev/null | head -5`;
        const output = execSync(command, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });
        if (output.trim()) {
          foundPatterns[method] += output.split('\n').filter(l => l.trim()).length;
        }
      } catch (e) {
        // Pattern not found, continue
      }
    }
  }

  // Determine most likely auth method
  const sortedMethods = Object.entries(foundPatterns)
    .sort((a, b) => b[1] - a[1])
    .filter(([_, count]) => count > 0);

  if (sortedMethods.length > 0) {
    const [method, count] = sortedMethods[0];
    results.method = method;
    results.confidence = count > 10 ? 'high' : count > 5 ? 'medium' : 'low';
  }

  // Determine required helpers based on auth method
  switch (results.method) {
    case 'magic-link':
      results.helpers = ['HELPER-002: Login helper (magic link)'];
      break;
    case 'oauth':
      results.helpers = ['HELPER-002: Login helper (OAuth)'];
      break;
    case 'session':
      results.helpers = ['HELPER-002: Login helper (session-based)'];
      break;
    case 'password':
      results.helpers = ['HELPER-002: Login helper (username/password)'];
      break;
    default:
      results.helpers = ['HELPER-002: Login helper (unknown method - requires investigation)'];
  }

  // Always require profile completion helper
  results.helpers.push('HELPER-004: Profile completion helper');

  return results;
}

// Run if executed directly
if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  const repoRoot = process.argv[2] || process.cwd();
  const result = detectAuthMethod(repoRoot);
  console.log(JSON.stringify(result, null, 2));
}

export { detectAuthMethod };

