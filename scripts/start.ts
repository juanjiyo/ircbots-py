#!/usr/bin/env node

/**
 * Script principal para iniciar todos los bots del ecosistema HeFESTo
 * 
 * Uso: npx ts-node scripts/start.ts [--bot <nombre>] [--all]
 */

import * as fs from 'fs';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';

// Cargar configuración
const configPath = path.join(__dirname, '..', 'config', 'bots.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));

// Procesar argumentos
const args = process.argv.slice(2);
const botName = args.includes('--bot') ? args[args.indexOf('--bot') + 1] : null;
const startAll = args.includes('--all') || !botName;

// Procesos activos
const processes: Map<string, ChildProcess> = new Map();

// Colores para la consola
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

function log(bot: string, message: string, level: 'info' | 'error' | 'warn' = 'info') {
  const timestamp = new Date().toISOString();
  const color = level === 'error' ? colors.red : level === 'warn' ? colors.yellow : colors.green;
  console.log(`${color}[${timestamp}] [${bot}]${colors.reset} ${message}`);
}

function getStartCommand(botConfig: any): { command: string; args: string[] } {
  const botType = botConfig.type;
  
  switch (botType) {
    case 'irc':
      return {
        command: 'bash',
        args: [path.join(__dirname, 'levantar_bots.sh')]
      };
    case 'telegram':
      return {
        command: 'python',
        args: [path.join(__dirname, 'telegram_agent_brain.py'), '--bot', botConfig.name]
      };
    default:
      throw new Error(`Tipo de bot desconocido: ${botType}`);
  }
}

async function startBot(name: string, botConfig: any): Promise<void> {
  if (!botConfig.enabled) {
    log(name, 'Bot deshabilitado, saltando...', 'warn');
    return;
  }

  try {
    const { command, args } = getStartCommand({ ...botConfig, name });
    
    log(name, `Iniciando bot ${name}...`);
    
    const child = spawn(command, args, {
      stdio: 'pipe',
      detached: false
    });

    child.stdout?.on('data', (data) => {
      log(name, data.toString().trim());
    });

    child.stderr?.on('data', (data) => {
      log(name, data.toString().trim(), 'error');
    });

    child.on('error', (error) => {
      log(name, `Error: ${error.message}`, 'error');
    });

    child.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        log(name, `Proceso terminado con código ${code}`, 'error');
        
        // Reiniciar si está configurado
        if (config.defaults.restartOnCrash) {
          log(name, 'Reiniciando bot...', 'warn');
          setTimeout(() => startBot(name, botConfig), 5000);
        }
      }
    });

    processes.set(name, child);
    log(name, `Bot ${name} iniciado correctamente`);
    
  } catch (error) {
    log(name, `Error al iniciar: ${error}`, 'error');
  }
}

async function startAllBots(): Promise<void> {
  console.log(`${colors.bright}${colors.cyan}=== Iniciando ecosistema HeFESTo ===${colors.reset}\n`);
  
  const bots = config.bots;
  
  for (const [name, botConfig] of Object.entries(bots)) {
    await startBot(name, botConfig);
  }
  
  console.log(`\n${colors.green}${colors.bright}Todos los bots iniciados.${colors.reset}`);
  console.log(`${colors.yellow}Presiona Ctrl+C para detener todos los bots.${colors.reset}\n`);
}

async function main(): Promise<void> {
  if (startAll) {
    await startAllBots();
  } else if (botName && config.bots[botName]) {
    await startBot(botName, config.bots[botName]);
  } else {
    console.error(`${colors.red}Error: Bot '${botName}' no encontrado en la configuración.${colors.reset}`);
    console.log(`\nBots disponibles:`);
    Object.keys(config.bots).forEach(name => {
      console.log(`  - ${name}`);
    });
    process.exit(1);
  }
}

// Manejar cierre graceful
process.on('SIGINT', () => {
  console.log(`\n${colors.yellow}Deteniendo todos los bots...${colors.reset}`);
  
  processes.forEach((child, name) => {
    log(name, 'Deteniendo...');
    child.kill('SIGTERM');
  });
  
  setTimeout(() => {
    console.log(`${colors.green}Todos los bots detenidos.${colors.reset}`);
    process.exit(0);
  }, 2000);
});

// Ejecutar
main().catch(error => {
  console.error(`${colors.red}Error fatal: ${error}${colors.reset}`);
  process.exit(1);
});
