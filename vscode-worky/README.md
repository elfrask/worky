# Worky para Visual Studio Code

Extension del lenguaje **Worky**: resaltado de sintaxis, snippets, autocompletado,
documentacion al pasar el cursor y reconocimiento de comandos de sistema operativo
para archivos `.worky`.

## Caracteristicas

- **Resaltado de sintaxis** para comentarios, variables (`$var`, `$~1`, `$*`),
  cadenas con interpolacion, numeros, operadores, herramientas (`/pause`, `/kill`, `/shell`),
  palabras clave de flujo (`in`, `run`, `os`, `set`, `export`) y comandos del shell.
- **Snippets** para cada flujo de control.
- **Autocompletado** contextual:
  - variables integradas y definidas por el usuario,
  - objetivos de sistema operativo tras `os:`,
  - herramientas `/`,
  - **comandos de sistema operativo** (Windows y Linux) dentro de los bloques `os`.
- **Hover** con documentacion de cada control de flujo, herramienta y comando.
- Comandos de la paleta: `Worky: Mostrar documentacion del lenguaje`,
  `Worky: Desplegar workspace` y `Worky: Abrir consola interactiva (--cli)`.

## Uso

Abre cualquier archivo `.worky`. La extension se activa sola. Escribe para ver
sugerencias, o pasa el cursor sobre una palabra para ver su documentacion.
Usa la paleta de comandos (`Ctrl+Shift+P`) y busca **Worky**.

## Consola interactiva (`worky --cli`)

Worky incluye una consola avanzada construida con [Textual](https://textual.textualize.io/)
que abre terminales reales (PTY) con pestanas y multiples instancias:

```bash
worky --cli                 # consola vacia con un shell
worky --cli workspace.worky # carga las instancias del archivo como pestanas
```

- **Ctrl+P** abre la paleta de comandos para: crear terminales (shell o con
  comando), hacer **fork** de la sesion actual, renombrar, cambiar de directorio
  (`cd` en caliente), enviar comandos, cerrar pestanas, abrir otro `.worky` y
  **guardar la configuracion actual en un archivo `.worky`**. Dentro de la paleta
  usa las **flechas arriba/abajo** para moverte por las opciones y `Enter` para
  elegir.
- Atajos: `Ctrl+T` nueva terminal, `Ctrl+N` fork, `Ctrl+W` cerrar,
  `Ctrl+Left`/`Ctrl+Right` cambiar de shell, `Ctrl+Q` salir.

Requiere las dependencias opcionales: `pip install "worky[cli]"`.

## El lenguaje Worky

Un archivo `.worky` es declarativo: describe que instancias desplegar y con que
comandos, y Worky lo materializa segun el sistema operativo.

### Comentarios

```worky
// comentario de una linea
```

### Variables

```worky
$name = "worky-space"
$args = ["$~1", "$~2", ...$*]   // argumentos de linea de comandos
$num  = 1
$sum  = 5 + $num                // matematicas: + - * /
$lista = ["uno", "dos", ...$args]
```

- `$~1`, `$~2`, ... son argumentos posicionales.
- `$*` contiene todos los argumentos.
- Se interpolan dentro de cadenas: `"hola $name"`.
- Escapes: `\n`, `\t`, `\"`, `\\`, `\$`.

### `in` - directorio de trabajo

Define el directorio base. Todo lo que contiene se despliega relativo a esa ruta.
Si el directorio no existe, Worky lo crea.

```worky
in "./app" {
  run "servidor" {
    os: all { pnpm run dev }
  }
}
```

### `run` - instancias

Crea una instancia del workspace (ventana, pestana o panel, segun el modo de
presentacion). El nombre es opcional; si se omite Worky asigna `run1`, `run2`, ...

```worky
run "terminal" { ... }   // instancia con nombre
run { ... }              // instancia anonima
```

### `os` - condicional por sistema

Ejecuta el bloque solo en el sistema indicado. Es lo que hace portable el
workspace. `all` se ejecuta en cualquier sistema.

```worky
run "shell" {
  os: win32 { cmd }
  os: linux { bash }
  os: all   { echo "listo" }
}
```

Valores: `win32` (Windows), `linux` (Linux), `darwin` (macOS), `all` (todos).

### `set` / `export` - variables de entorno

```worky
os: win32 {
  set NODE_ENV = "development"
}
os: linux {
  export NODE_ENV = "development"
}
```

### Comandos

Toda linea dentro de un bloque `os` que no empiece por `/` se ejecuta en el shell
de la instancia. El autocompletado reconoce comandos de Windows y Linux.

```worky
os: all {
  pnpm run dev
}
```

### Herramientas de Worky (`/`)

- `/pause` - espera a que el usuario pulse Enter.
- `/kill "nombre"` - cierra la instancia indicada.
- `/kill all` - cierra todas las instancias de la ejecucion actual.
- `/shell` - abre el shell del sistema (cmd en Windows, bash en Linux).
- `/shell <comando>` - ejecuta el comando en el shell y lo deja abierto al terminar.
- `/shell { ... }` - ejecuta varios comandos en el shell y lo deja abierto.

```worky
run "dev" {
  os: all {
    /shell {
      git status
      git pull
    }
    /shell pnpm run dev
  }
}

run {
  os: all {
    /pause
    /kill "servidor"
    /kill all
  }
}
```

## Ejemplo completo

```worky
$name = "worky-space"

in "./" {
  run "terminal" {
    os: win32 {
      set NODE_ENV = "development"
      cmd
    }
    os: linux {
      export NODE_ENV = "development"
      bash
    }
    os: all {
      echo "instancia lista"
    }
  }

  run "servidor" {
    os: all { pnpm run dev }
  }
}

in "./app" {
  run "terminal-app" {
    os: win32 { cmd }
    os: linux { bash }
  }
}

in "./" {
  run {
    os: all {
      echo "pulsa Enter para cerrar todo"
      /pause
      /kill all
    }
  }
}
```

## Configuracion

- `worky.completions.osCommands` (bool, por defecto `true`): activar el
  autocompletado de comandos de sistema operativo.
- `worky.completions.preferContext` (bool, por defecto `true`): priorizar los
  comandos del sistema del bloque `os` donde esta el cursor.

## Desarrollo

```bash
npm install -g @vscode/vsce
vsce package
code --install-extension worky-0.2.0.vsix
```

## Estructura

```
vscode-worky/
  package.json
  language-configuration.json
  syntaxes/worky.tmLanguage.json
  snippets/worky.json
  src/extension.js
  src/data.js
  README.md
```
