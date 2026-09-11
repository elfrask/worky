"use strict";

const vscode = require("vscode");
const data = require("./data");

/**
 * Detecta el bloque `os:` que contiene la posicion del cursor.
 * Devuelve "win32" | "linux" | "darwin" | "all" | null.
 */
function osContextAt(document, position) {
  const stack = [];
  for (let line = 0; line <= position.line; line++) {
    const text = document.lineAt(line).text;
    const limit = line === position.line ? position.character : text.length;
    for (let i = 0; i < limit; i++) {
      const ch = text[i];
      if (ch === "{") {
        const head = text.slice(0, i);
        const match = /os\s*:\s*(win32|linux|darwin|all)/.exec(head);
        stack.push(match ? match[1] : null);
      } else if (ch === "}") {
        stack.pop();
      }
    }
  }
  for (let i = stack.length - 1; i >= 0; i--) {
    if (stack[i]) return stack[i];
  }
  return null;
}

function userVariables(document) {
  const names = new Set();
  const text = document.getText();
  const re = /\$([A-Za-z_]\w*)\s*=/g;
  let match;
  while ((match = re.exec(text))) {
    names.add(match[1]);
  }
  return Array.from(names);
}

function commandMap() {
  const map = new Map();
  for (const group of Object.keys(data.OS_COMMANDS)) {
    for (const entry of data.OS_COMMANDS[group]) {
      const name = entry[0];
      const info = { doc: entry[1], group: entry[2] || "cmd" };
      if (!map.has(name)) {
        map.set(name, info);
      }
      const base = name.split(/\s+/)[0];
      if (base !== name && !map.has(base)) {
        map.set(base, info);
      }
    }
  }
  return map;
}

const COMMAND_INDEX = commandMap();

function osCommandsFor(context) {
  const groups = [];
  if (context === "win32") {
    groups.push(["win32", 0]);
    groups.push(["common", 1]);
    groups.push(["linux", 2]);
  } else if (context === "linux" || context === "darwin") {
    groups.push(["linux", 0]);
    groups.push(["common", 1]);
    groups.push(["win32", 2]);
  } else {
    groups.push(["common", 0]);
    groups.push(["win32", 1]);
    groups.push(["linux", 1]);
  }
  const out = [];
  for (const [group, rank] of groups) {
    for (const entry of data.OS_COMMANDS[group]) {
      out.push({ name: entry[0], doc: entry[1], group: entry[2] || "cmd", rank });
    }
  }
  return out;
}

function makeCompletion(context) {
  return {
    provideCompletionItems(document, position) {
      const config = vscode.workspace.getConfiguration("worky");
      const linePrefix = document.lineAt(position.line).text.slice(0, position.character);
      const items = [];

      const toolMatch = /(^|[{;])\s*\/([A-Za-z_]\w*)?$/.exec(linePrefix);
      if (toolMatch) {
        const typed = toolMatch[2] || "";
        for (const key of Object.keys(data.TOOLS)) {
          const tool = data.TOOLS[key];
          const item = new vscode.CompletionItem(tool.label, vscode.CompletionItemKind.Function);
          item.detail = tool.detail;
          item.documentation = new vscode.MarkdownString(tool.doc);
          item.insertText = new vscode.SnippetString(key === "kill" ? 'kill ${1:all}' : key);
          item.range = new vscode.Range(position.translate(0, -typed.length - 1), position);
          items.push(item);
        }
        return items;
      }

      const osMatch = /os\s*:\s*(\w*)$/.exec(linePrefix);
      if (osMatch) {
        for (const target of data.OS_TARGETS) {
          const item = new vscode.CompletionItem(target.label, vscode.CompletionItemKind.EnumMember);
          item.detail = "Sistema operativo";
          item.documentation = new vscode.MarkdownString(target.doc);
          items.push(item);
        }
        return items;
      }

      const varMatch = /\$([A-Za-z_]\w*)?$/.exec(linePrefix);
      if (varMatch) {
        const token = varMatch[0];
        const start = position.translate(0, -token.length);
        for (const builtin of data.BUILTIN_VARS) {
          const item = new vscode.CompletionItem(builtin.label, vscode.CompletionItemKind.Variable);
          item.detail = "Variable integrada";
          item.documentation = new vscode.MarkdownString(builtin.doc);
          item.range = new vscode.Range(start, position);
          items.push(item);
        }
        for (const name of userVariables(document)) {
          const item = new vscode.CompletionItem("$" + name, vscode.CompletionItemKind.Variable);
          item.detail = "Variable definida";
          item.range = new vscode.Range(start, position);
          items.push(item);
        }
        return items;
      }

      for (const key of Object.keys(data.KEYWORDS)) {
        const kw = data.KEYWORDS[key];
        const item = new vscode.CompletionItem(kw.label, vscode.CompletionItemKind.Keyword);
        item.detail = kw.detail;
        item.documentation = new vscode.MarkdownString(kw.doc);
        item.sortText = "0" + kw.label;
        items.push(item);
      }

      for (const target of data.OS_TARGETS) {
        const item = new vscode.CompletionItem(target.label, vscode.CompletionItemKind.EnumMember);
        item.detail = "Sistema operativo";
        item.documentation = new vscode.MarkdownString(target.doc);
        item.sortText = "1" + target.label;
        items.push(item);
      }

      for (const name of userVariables(document)) {
        const item = new vscode.CompletionItem("$" + name, vscode.CompletionItemKind.Variable);
        item.detail = "Variable definida";
        item.sortText = "2" + name;
        items.push(item);
      }

      if (config.get("completions.osCommands", true)) {
        const context = config.get("completions.preferContext", true)
          ? osContextAt(document, position)
          : null;
        for (const entry of osCommandsFor(context)) {
          const item = new vscode.CompletionItem(entry.name, vscode.CompletionItemKind.Function);
          item.detail = entry.group;
          item.documentation = new vscode.MarkdownString(entry.doc);
          item.sortText = String(3 + entry.rank) + entry.name;
          items.push(item);
        }
      }

      return items;
    },
  };
}

function makeHover() {
  return {
    provideHover(document, position) {
      const range = document.getWordRangeAtPosition(position, /[$\w~/.*-]+/);
      if (!range) {
        return undefined;
      }
      const word = document.getText(range);

      const toolKey = word.startsWith("/") ? word.slice(1) : null;
      if (toolKey && data.TOOLS[toolKey]) {
        return new vscode.Hover(
          new vscode.MarkdownString("**" + data.TOOLS[toolKey].detail + "**\n\n" + data.TOOLS[toolKey].doc),
          range
        );
      }

      if (data.KEYWORDS[word]) {
        const kw = data.KEYWORDS[word];
        return new vscode.Hover(
          new vscode.MarkdownString("### " + kw.detail + "\n\n" + kw.doc),
          range
        );
      }

      const target = data.OS_TARGETS.find((t) => t.label === word);
      if (target) {
        return new vscode.Hover(
          new vscode.MarkdownString("**os: " + target.label + "**\n\n" + target.doc),
          range
        );
      }

      const builtin = data.BUILTIN_VARS.find((v) => v.label === word);
      if (builtin) {
        return new vscode.Hover(
          new vscode.MarkdownString("**" + builtin.label + "**\n\n" + builtin.doc),
          range
        );
      }

      if (word.startsWith("$") && word.length > 1) {
        return new vscode.Hover(
          new vscode.MarkdownString("Variable `" + word + "`. Se interpola dentro de cadenas `\"...\"`."),
          range
        );
      }

      if (COMMAND_INDEX.has(word)) {
        const info = COMMAND_INDEX.get(word);
        return new vscode.Hover(
          new vscode.MarkdownString("**Comando** (`" + info.group + "`)\n\n" + info.doc),
          range
        );
      }

      return undefined;
    },
  };
}

function buildDocs() {
  const lines = [];
  lines.push("# Lenguaje Worky");
  lines.push("");
  lines.push("Archivo declarativo (`.worky`) para desplegar un workspace en instancias de terminal.");
  lines.push("");
  lines.push("## Flujos de control");
  lines.push("");
  lines.push("### `in \"directorio\" { ... }`");
  lines.push("Define el directorio de trabajo. Lo contenido se despliega relativo a esa ruta.");
  lines.push("");
  lines.push("### `run \"nombre\" { ... }`");
  lines.push("Crea una instancia (ventana, pestana o panel segun el modo). El nombre es opcional.");
  lines.push("");
  lines.push("### `os: win32 | linux | darwin | all { ... }`");
  lines.push("Ejecuta el bloque solo en el sistema indicado. Hace el workspace portable.");
  lines.push("");
  lines.push("### `set CLAVE = valor` / `export CLAVE = valor`");
  lines.push("Variables de entorno para Windows (`set`) y Linux/macOS (`export`).");
  lines.push("");
  lines.push("### Variables y matematicas");
  lines.push("`$name = \"valor\"`, arrays `[\"a\", \"b\"]`, spread `...$*`, y operaciones `+ - * /`.");
  lines.push("Argumentos: `$~1`, `$~2`, ..., `$*`.");
  lines.push("");
  lines.push("### Comandos de Worky (`/`)");
  lines.push("- `/pause` espera a pulsar Enter.");
  lines.push("- `/kill \"nombre\"` cierra una instancia; `/kill all` las cierra todas.");
  lines.push("");
  lines.push("## Comandos de sistema");
  lines.push("Cualquier linea que no empiece por `/` se ejecuta en el shell de la instancia.");
  lines.push("El autocompletado y el hover reconocen comandos de Windows y Linux dentro de cada `os:`.");
  lines.push("");
  lines.push("## Ejemplo");
  lines.push("```worky");
  lines.push("in \"./\" {");
  lines.push("  run \"servidor\" {");
  lines.push("    os: win32 { pnpm run dev }");
  lines.push("    os: linux { export NODE_ENV = \"dev\" }");
  lines.push("    os: all { /pause }");
  lines.push("  }");
  lines.push("}");
  lines.push("```");
  return lines.join("\n");
}

function activate(context) {
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider("worky", makeCompletion(), "$", "/", ":", " ")
  );
  context.subscriptions.push(vscode.languages.registerHoverProvider("worky", makeHover()));

  context.subscriptions.push(
    vscode.commands.registerCommand("worky.showDocs", async () => {
      const doc = await vscode.workspace.openTextDocument({
        language: "markdown",
        content: buildDocs(),
      });
      await vscode.window.showTextDocument(doc, { preview: true });
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("worky.run", () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.document.languageId !== "worky") {
        vscode.window.showWarningMessage("Abre un archivo .worky para desplegar el workspace.");
        return;
      }
      editor.document.save();
      const terminal = vscode.window.createTerminal("Worky");
      terminal.show();
      terminal.sendText('worky "' + editor.document.fileName + '"');
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("worky.cli", () => {
      const editor = vscode.window.activeTextEditor;
      const file =
        editor && editor.document.languageId === "worky" ? ' "' + editor.document.fileName + '"' : "";
      const terminal = vscode.window.createTerminal("Worky CLI");
      terminal.show();
      terminal.sendText("worky --cli" + file);
    })
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
