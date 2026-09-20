# worky

Despliega **workspaces declarativos** definidos en archivos `.worky`: describe que
instancias de terminal quieres y con que comandos, y worky lo materializa en
Windows Terminal (pestanas, paneles o ventanas) o en el emulador de terminal de
Linux.

Incluye un mini-lenguaje propio, herramientas multiplataforma (`/pause`, `/kill`,
`/shell`), una condicion por sistema operativo (`os:`) y una **consola interactiva**
(`worky --cli`) con pestanas, terminales embebidas reales y paleta de comandos.

## Caracteristicas

- Mini-lenguaje `.worky` con variables, interpolacion, argumentos, matematicas y arrays.
- Condicional por sistema: `os: win32 | linux | darwin | all`.
- Modos de presentacion: pestanas aqui, pestanas, una ventana con paneles o ventanas separadas.
- Herramientas: `/pause`, `/kill` y `/shell` (shell del SO, con comando o con bloque).
- Scripts generados por instancia (`.cmd` / `.sh`) y cierre de procesos por `--kill`.
- Consola `--cli` con Textual: pestanas, PTY reales, fork, `Ctrl+P` y guardado a `.worky`.
- Extension de VS Code con resaltado, snippets, autocompletado y hover.

## Instalacion

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[cli,dev]"
```

- Sin extras basta para desplegar workspaces.
- El extra `cli` instala la consola `worky --cli` (`textual`, `pyte`, `pywinpty`).
- El extra `dev` instala `pytest`.

En Windows tambien puedes usar el lanzador `worky.cmd`, que reutiliza el `.venv`
del proyecto si existe.

## Uso

```bash
worky workspace.worky          # despliega segun el modo por defecto
worky                          # busca workspace.worky o el primer *.worky
worky workspace.worky -- args  # pasa argumentos al script ($~1, $~2, $*)
```

Modos de presentacion:

| Opcion | Descripcion |
| --- | --- |
| `--tabs-here` | Pestanas en la ventana de Windows Terminal actual (por defecto). |
| `--tabs` | Una ventana nueva con una pestana por instancia. |
| `--one-window` | Todos los paneles acoplados en una sola ventana. |
| `--windows` | Una ventana por instancia, auto-organizadas. |

Opciones:

| Opcion | Descripcion |
| --- | --- |
| `--layout auto\|columns\|rows\|grid` | Disposicion de paneles/ventanas. |
| `--dry-run` | Muestra que se ejecutaria sin desplegar. |
| `--dump` | Muestra los scripts generados. |

Control:

```bash
worky --kill <nombre> --run <id>
worky --kill-all --run <id>
```

## El lenguaje `.worky`

Un archivo `.worky` es declarativo. Los comentarios empiezan con `//`.

### Variables y expresiones

```worky
$name = "worky-space"
$args = ["$~1", "$~2", ...$*]   // argumentos de linea de comandos
$num  = 1
$sum  = 5 + $num                // + - * /
$lista = ["uno", "dos", ...$args]
```

- `$~1`, `$~2`, ... son argumentos posicionales y `$*` contiene todos.
- Se interpolan dentro de cadenas: `"hola $name"`.
- Escapes: `\n`, `\t`, `\"`, `\\`, `\$`.

### `in` - directorio de trabajo

Define el directorio base (lo crea si no existe). Los `run` que contiene se
despliegan relativos a esa ruta.

```worky
in "./app" {
  run "servidor" { pnpm run dev }
}
```

### `run` - instancias

Crea una instancia (pestana, panel o ventana segun el modo). El nombre es opcional:
si se omite, worky asigna `run1`, `run2`, ...

```worky
run "terminal" { ... }
run { ... }
```

### `os` - condicional por sistema

Ejecuta el bloque solo en el sistema indicado. `all` se ejecuta en cualquier
sistema (y despues del bloque propio).

```worky
run "shell" {
  os: win32 { cmd }
  os: linux { bash }
  os: all   { echo "listo" }
}
```

### `set` / `export` - variables de entorno

```worky
os: win32 { set NODE_ENV = "development" }
os: linux { export NODE_ENV = "development" }
```

### Comandos

Toda linea dentro de un bloque `os` que no empiece por `/` se ejecuta en el shell
de la instancia.

```worky
os: all { pnpm run dev }
```

### Herramientas (`/`)

- `/pause` - espera a que el usuario pulse Enter.
- `/kill "nombre"` - cierra la instancia indicada.
- `/kill all` - cierra todas las instancias de la ejecucion actual.
- `/shell` - abre el shell del sistema (`cmd` en Windows, `bash` en Linux).
- `/shell <comando>` - ejecuta el comando y **deja el shell abierto** al terminar.
- `/shell { ... }` - ejecuta varios comandos y deja el shell abierto.

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
```

## Consola interactiva (`worky --cli`)

Consola avanzada construida con [Textual](https://textual.textualize.io/) que abre
terminales reales (PTY) con pestanas:

```bash
worky --cli                  # consola vacia con un shell
worky --cli workspace.worky  # carga las instancias del archivo como pestanas
```

- `Ctrl+P` abre la paleta: nueva terminal (shell o con comando), **fork** de la
  sesion actual, renombrar, cambiar de directorio, enviar comandos, cerrar,
  abrir otro `.worky` y **guardar la configuracion actual en un `.worky`**.
  Dentro de la paleta, las flechas arriba/abajo mueven la seleccion y `Enter` elige.
- Atajos: `Ctrl+T` nueva, `Ctrl+N` fork, `Ctrl+W` cerrar,
  `Ctrl+Left`/`Ctrl+Right` cambiar de shell, `Ctrl+Q` salir.

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

## Estructura del proyecto

```
worky/
  pyproject.toml
  worky.cmd
  workspace.worky
  src/worky/
    cli.py            # entrada de linea de comandos
    lexer.py          # analizador lexico
    parser.py         # analizador sintactico
    nodes.py          # nodos del AST
    interpreter.py    # interpretacion y construccion de instancias
    render.py         # generacion de scripts y herramientas
    platforms.py      # deteccion de plataforma
    runtime.py        # re-invocacion de worky
    kill.py           # cierre de procesos
    errors.py
    deployers/        # despliegue en Windows Terminal y Linux
    tui/              # consola --cli (pty, emulador, widget, paleta, app)
  tests/              # pruebas pytest
  vscode-worky/       # extension de VS Code
```

## Desarrollo

```bash
pytest                 # 33 pruebas
pip install -e ".[cli,dev]"
```

La extension de VS Code se empaqueta en `vscode-worky/`:

```bash
npx @vscode/vsce package
code --install-extension worky-0.2.0.vsix
```

## Licencia

[MIT](LICENSE) © 2026 elfrask
