<p align="center"><img src="docs/style/hero.png" alt="mixin-stubber — auto-Mixin stubs for Minecraft" width="100%"></p>

<p align="center">
  <a href="README.ru.md"><img src="docs/style/pill-ru.png" alt="README RU" height="42"></a>
  <a href="https://github.com/Celine1337/mixin-stubber/releases"><img src="docs/style/pill-release.png" alt="Releases" height="42"></a>
  <a href="https://github.com/Celine1337/mixin-stubber/actions/workflows/ci.yml"><img src="docs/style/pill-ci.png" alt="CI" height="42"></a>
  <a href="LICENSE"><img src="docs/style/pill-license.png" alt="MIT" height="42"></a>
</p>

<img src="docs/style/sec-about-en.png" alt="About" width="100%">

Paste a vanilla Minecraft method signature — get a ready-to-use SpongePowered
`@Mixin` class: `@Inject` / `@Redirect`, `at = @At(...)`, `CallbackInfo` /
`CallbackInfoReturnable<T>`, imports and handler parameters, all wired up.

Single file, standard library only, Python 3.9+. Understands Mojmap,
intermediary and SRG names. Fabric or Forge — the generated stub is plain
Mixin, drop it into your mod and fill in the `TODO`.

<img src="docs/style/sec-features-en.png" alt="Features" width="100%">

- **Five signature formats** — ASM, `Class#method(descriptor)`, readable Java,
  return-first, and bare intermediary/SRG names (see below).
- **`@Inject`** at `HEAD`, `TAIL`, `RETURN` or `INVOKE`; auto `cancellable = true`
  for non-void `RETURN`, with a commented `cir.setReturnValue(...)` carrying a
  type-correct default (`0`, `0L`, `0.0F`, `false`, `null`, ...).
- **`@Redirect`** with a fully built `@At(value = "INVOKE", target = "L...;->m(...)R")`,
  receiver instance + target args as handler parameters, and a passthrough call
  as the starting body. `--target-static` for static targets.
- **Overload-safe `method` strings** — JVM descriptors are reconstructed from
  readable types whenever the packages are known.
- **Correct callback types** — `CallbackInfo` for void, boxed
  `CallbackInfoReturnable<Integer>` / `<FoodData>` / ... otherwise.
- **Import management** — mixin annotations and every referenced type are
  imported; unresolvable simple names get a `// TODO: add imports for: ...` list.
- Constructors (`<init>`, `<clinit>`), generics-aware argument splitting, arrays.
- stdout or `--out File.java` (`--force` to overwrite); interactive prompt when
  run without arguments.

<img src="docs/style/sec-formats-en.png" alt="Signature formats" width="100%">

| Format | Example |
| --- | --- |
| ASM | `Lnet/minecraft/client/Minecraft;->runTick()V` |
| Hash + JVM descriptor | `net.minecraft.client.Minecraft#runTick()V` |
| Readable Java | `net.minecraft.client.Minecraft.runTick(boolean)` |
| Return-first | `int net.minecraft.util.Mth#clamp(int,int,int)` |
| Bare (intermediary / SRG) | `net.minecraft.class_310#method_1523` |

- JVM descriptors (`(IF)Ljava/lang/String;`, arrays, primitives) are parsed and
  turned back into Java types for the handler signature.
- Readable types rebuild the descriptor when every type is fully qualified or
  primitive; otherwise the `method` string falls back to the bare name.
- Bare names (no parentheses) generate a stub plus a
  `// NOTE: no descriptor given - add one if the target method is overloaded`
  comment — handy for intermediary/SRG where you only have `class_310#method_1523`.
- `INVOKE` / redirect targets must carry a return type (`int pkg.Cls#m(int)` or
  `Lpkg/Cls;->m(I)I`); guessing `V` would silently produce a broken stub.

<img src="docs/style/sec-stack-en.png" alt="Tech stack" width="100%">

<img src="docs/style/chips.png" alt="Python 3.9+, unittest, JVM descriptors; GitHub Actions, Pillow, SpongePowered Mixin" width="100%">

<img src="docs/style/sec-quick-en.png" alt="Quick start" width="100%">

```console
$ python mixin_stubber.py "net.minecraft.world.entity.player.Player#tick()V"
```

```java
package com.example.mixin;

import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Player.class)
public abstract class PlayerMixin {

    @Inject(method = "tick()V", at = @At("HEAD"))
    private void onTickHead(CallbackInfo ci) {
        // TODO: injected at HEAD of Player#tick()V
    }
}
```

No install, no dependencies — clone and run.

| Flag | Meaning |
| --- | --- |
| `--mode` | `inject` (default) or `redirect` |
| `--at` | injection point for inject; redirect always uses `INVOKE` |
| `--target` | called method for `INVOKE` / redirect, any signature format |
| `--target-static` | redirect target is static (no receiver parameter) |
| `--static` | target method is static → static handler |
| `--cancellable` | force `cancellable = true` |
| `--package` | mixin package (default `com.example.mixin`) |
| `--name` | mixin class name (default `<Target>Mixin`) |
| `--out` / `--force` | write to a file / overwrite it |

Redirect: the handler receives the receiver instance (`Gui gui`) followed by
the target's arguments, returns the target's return type, and starts with a
passthrough call so the stub compiles and behaves identically until you edit it.

```console
# non-void RETURN: CallbackInfoReturnable + cancellable + setReturnValue hint
$ python mixin_stubber.py "net.minecraft.world.entity.player.Player#getFoodData()Lnet/minecraft/world/food/FoodData;" --at RETURN

# static target: no receiver, static passthrough
$ python mixin_stubber.py "net.minecraft.world.entity.player.Player#tick()V" --mode redirect \
    --target "int net.minecraft.util.Mth#clamp(int,int,int)" --target-static

# constructor injection
$ python mixin_stubber.py "net.minecraft.world.entity.player.Player#<init>(Lnet/minecraft/world/level/Level;)V"

# straight into your mod source tree
$ python mixin_stubber.py "net.minecraft.class_310#method_1523" --package dev.mymod.mixin --out src/main/java/dev/mymod/mixin/MinecraftClientMixin.java
```

<img src="docs/style/sec-shots-en.png" alt="Screenshots" width="100%">

![inject example](docs/inject.png)

![redirect example](docs/redirect.png)

<img src="docs/style/sec-tests-en.png" alt="Tests" width="100%">

```console
$ python -m unittest discover -s tests -v
```

33 tests cover parsing (all formats, arrays, generics, constructors, bad input)
and generation (inject/redirect, static, cancellable, imports, CLI).
Screenshots and card assets are regenerable:

```console
$ pip install pillow
$ python tools/make_shots.py        # docs/inject.png, docs/redirect.png
$ python tools/make_style.py tools/style.json docs/style
```

<img src="docs/style/stats.png" alt="33 tests, 3 OSes in CI, v1.0.0" width="100%">

[MIT](LICENSE) © Celine1337
