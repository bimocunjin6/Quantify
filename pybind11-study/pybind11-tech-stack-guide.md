# pybind11 技术栈学习笔记：从一行 `add()` 说起

> 这是一份 **个人学习笔记**，记录我学习 pybind11 技术栈的过程、理解方式、踩过的坑，以及以后再写绑定时需要注意的地方。
>
> 起点是仓库里那个已经跑通的极小工程（`..`），然后顺着"原理 → 环境 → 构建 → 函数绑定 → 类绑定 → 类型转换 → 异常与 GIL → 嵌入"这条线，把整个技术栈过一遍。
>
> 笔记环境：Windows + MinGW GCC 16.2.0 + Python 3.12.0 + pybind11 **v3.2.0**（仓库内 `..`）+ CMake 4.4.4 + Ninja 1.13.2。文中标注"**实测**"的结论都是我自己编译、运行、验证过的结果；代码片段可以直接照抄。

---

## 目录

- [第 0 章 起点：本仓库里已经有一个能跑的 pybind11 工程](#第-0-章-起点本仓库里已经有一个能跑的-pybind11-工程)
- [第 1 章 为什么需要 pybind11：混合编程的动机](#第-1-章-为什么需要-pybind11混合编程的动机)
- [第 2 章 技术选型：六大桥接方案横向对比](#第-2-章-技术选型六大桥接方案横向对比)
- [第 3 章 原理剖析：pybind11 到底做了什么](#第-3-章-原理剖析pybind11-到底做了什么)
- [第 4 章 环境搭建：Windows + MinGW + Python 3.12 实战](#第-4-章-环境搭建windows--mingw--python-312-实战)
- [第 5 章 第一个扩展逐行解剖](#第-5-章-第一个扩展逐行解剖)
- [第 6 章 构建系统详解：CMake 与四条集成路线](#第-6-章-构建系统详解cmake-与四条集成路线)
- [第 7 章 函数绑定全解](#第-7-章-函数绑定全解)
- [第 8 章 类与对象绑定全解](#第-8-章-类与对象绑定全解)
- [第 9 章 类型转换体系](#第-9-章-类型转换体系)
- [第 10 章 异常、GIL 与生命周期](#第-10-章-异常gil-与生命周期)
- [第 11 章 嵌入 Python：把解释器装进 C++ 程序](#第-11-章-嵌入-python把解释器装进-c-程序)
- [第 12 章 学习经验与注意事项](#第-12-章-学习经验与注意事项)
- [第 13 章 踩坑记录与 FAQ](#第-13-章-踩坑记录与-faq)
- [附录 常用 API 速查表](#附录-常用-api-速查表)

---

## 第 0 章 起点：本仓库里已经有一个能跑的 pybind11 工程

在开始讲理论之前，先把学习者脚下已有的东西看清楚。本仓库 `..` 目录就是一个**最小完整闭环**的 pybind11 项目：

```text
pybind11/
├── CMakelists.txt                  # 构建脚本（注意官方写法是 CMakeLists.txt）
├── hello.cpp                       # 唯一的绑定源文件：一个 add()
├── test.cpp                        # 与绑定无关的纯 C++ Hello World
├── main.py                         # Python 侧调用：import HelloWorld
├── log.txt                         # 一次真实的构建全过程日志（含踩坑）
├── HelloWorld.cp312-win_amd64.pyd  # 编译产物（已放在源码目录，可直接 import）
├── build/                          # CMake/Ninja 构建目录
└── extern/pybind11/                # vendored 的 pybind11 源码，版本 v3.2.0
```

### 0.1 三行核心代码

绑定侧（`..`，共 11 行）：

```cpp
#include <pybind11/pybind11.h>

int add(int i, int j) {
    return i + j;
}

PYBIND11_MODULE(HelloWorld, m) {
    m.doc() = "pybind11 example plugin"; // optional module docstring

    m.def("add", &add, "A function that adds two numbers");
}
```

Python 侧（`..`）：

```python
import HelloWorld as hw

print(hw.add(1, 2))   # 输出 3
```

构建侧（`..`）：

```cmake
cmake_minimum_required(VERSION 3.23)
project(HelloWorld)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(MINGW)
    # MinGW 环境下，强制静态链接所有库
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -static")
elseif(MSVC)
    # MSVC (Visual Studio) 环境下，使用静态运行库
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

add_subdirectory(extern/pybind11)
pybind11_add_module(HelloWorld hello.cpp)
```

### 0.2 它确实跑通了：来自 log.txt 的真实证据

`log.txt` 里保存了一次真实的"踩坑 → 修正 → 成功"全过程。其中最典型的一个错误值得所有人先看一遍：

```text
PS D:\...\Quantify\pybind11> mkdir build
PS D:\...\Quantify\pybind11> cmake ..
CMake Warning:
  Ignoring extra path from command line:
   ".."
CMake Error: The source directory "D:/study/programming/python/project/Quantify"
does not appear to contain CMakeLists.txt.
```

**原因**：`cmake ..` 必须在 `build/` 目录里执行（此时 `..` 才是工程根）。在工程根目录再执行 `cmake ..`，`..` 指向了上一级的 `Quantify/`，那里没有 `CMakeLists.txt`。

修正后：

```text
PS D:\...\pybind11> cd .\build\
PS D:\...\pybind11\build> cmake ..
-- Building for: Ninja
-- The C compiler identification is GNU 16.2.0
-- The CXX compiler identification is GNU 16.2.0
-- pybind11 v3.2.0
-- Found Python: D:/ruanjian/Python/Python3/python.exe (found suitable version "3.12.0", minimum required is "3.9") found components: Interpreter Development.Module Development.Embed
Using compatibility mode for Python, set PYBIND11_FINDPYTHON to NEW/OLD to silence this message
-- pybind11::lto disabled (problems with undefined symbols for MinGW for now)
-- pybind11::thin_lto disabled (problems with undefined symbols for MinGW for now)
-- Configuring done (3.5s)

PS D:\...\pybind11\build> cmake --build . --config Release
[2/2] Linking CXX shared module HelloWorld.cp312-win_amd64.pyd

PS D:\...\pybind11> python
>>> import HelloWorld
>>> HelloWorld.add(1, 2)
3
```

这段日志里暗含 5 个关键知识点，后文都会展开：

| 日志线索 | 含义 | 详见 |
| --- | --- | --- |
| `pybind11 v3.2.0` | 用的是 v3 系列（相对 v2 有若干破坏性变更） | 第 6.6、17 章 |
| `Found Python: ... 3.12.0` | CMake 自动定位 Python 解释器与开发头文件 | 第 4、6 章 |
| `PYBIND11_FINDPYTHON` 兼容模式警告 | 新旧两套 FindPython 逻辑并存 | 第 6.4 节 |
| `lto disabled (problems with undefined symbols for MinGW)` | MinGW 下自动关闭 LTO，属预期行为 | 第 6.5 节 |
| `HelloWorld.cp312-win_amd64.pyd` | ABI 标签决定文件名，不可随意改名/复用 | 第 6.6 节 |

### 0.3 我在本机复现的结果

```powershell
PS> cd pybind11
PS> python -c "import HelloWorld as hw; print(hw.add(1,2)); print(hw.add.__doc__)"
3
add(arg0: typing.SupportsInt | typing.SupportsIndex, arg1: typing.SupportsInt | typing.SupportsIndex) -> int

A function that adds two numbers
```

这里出现了一个**很多老教程不会提到的新特性**：pybind11 v3 会为绑定函数自动生成 Python 类型注解（`typing.SupportsInt | typing.SupportsIndex`），直接体现在 `__doc__` 里。这意味着你的 IDE 补全、`help()`、静态类型检查都能受益——第 9.6 节会讲如何利用 `..`。

---

## 第 1 章 为什么需要 pybind11：混合编程的动机

### 1.1 两种语言的天然分工

Python 的强项与 C++ 的强项几乎正交：

| 维度 | Python | C++ |
| --- | --- | --- |
| 开发效率 | 极高 | 中 |
| 运行速度（数值循环） | 慢（10~1000×） | 快 |
| 生态（数据分析、AI、脚本胶水） | 极强 | 弱 |
| 底层控制（内存布局、SIMD、硬件） | 弱 | 强 |
| 部署形态 | 解释器 + wheel | 原生二进制 |
| 并发 | GIL 限制（传统构建下） | 真并行 |

于是几乎所有"性能敏感 + 生态依赖"的系统都走向同一形态：**Python 负责调度与业务，C++ 负责热点内层循环**。你熟悉的 NumPy、PyTorch、OpenCV、pandas、SciPy、Polars、pydantic-core、Tokenizers 都是这个形态。

### 1.2 什么时候真的需要写 C++ 扩展

先泼一盆冷水：**绝大多数 Python 性能问题不需要写 C++**。请按下面的顺序做决策：

```text
1. 换算法/数据结构                      ── 收益最大，风险最小
2. 向量化（NumPy 数组运算，避免 Python for）
3. 用现成的高性能库（NumPy/Numba/Cython/JAX）
4. 多进程 / 分块并行
5. 写 C++ 扩展（pybind11）              ── 本文主题
```

真正需要 pybind11 的典型场景：

1. **已有 C++ 代码资产**：量化回测引擎、风控计算库、仿真内核，希望直接在 Python 里调用，而不是重写。
2. **NumPy 也救不了的循环**：带状态、带分支、带自适应步长、带事件触发的逐 tick 计算（典型：回测撮合、逐笔风控、路径依赖期权定价）。
3. **需要精确控制内存布局与缓存**：手工 SoA 布局、`float32` 打包、SIMD 友好结构。
4. **需要调用系统/硬件/第三方 C SDK**：券商柜台 API、加密库、CUDA/HIP 内核封装。
5. **GIL 之外的真并行**：释放 GIL 后跑多线程 C++。
6. **把 Python 嵌入 C++ 宿主**：游戏、CAD、EDA、工业软件做脚本层（第 11 章）。

### 1.3 用一副"决策图"锁定 pybind11

```text
你要把 C++ 暴露给 Python 吗？
├─ 否，只是想加速 Python 逻辑 ──► 先用 NumPy/Numba/Cython，多数情况够了
└─ 是
   ├─ 目标语言也是 C 风格且你愿意手写 C-API ──► ctypes/cffi 可以应付简单函数
   ├─ 需要"类/继承/STL/异常/智能指针"完整语义 ──► pybind11（本文）
   └─ 需要极致可定制、愿意接受学习成本 ──► Cython / 手写 CPython C-API
```

pybind11 的定位非常清晰：**用现代 C++ 的模板元编程，把"手写 CPython C-API"这件脏活压缩成声明式的一行行 `.def()`**。

---

## 第 2 章 技术选型：六大桥接方案横向对比

在动手前，先把候选方案看清楚。这张表是本文最重要的一张"省时间"的表：

| 方案 | 绑定方式 | 类型/类支持 | 性能 | 学习成本 | 编译需求 | 典型用户 |
| --- | --- | --- | --- | --- | --- | --- |
| **ctypes** | 运行时 dlopen，手写签名 | 仅 C 函数/结构体，无 C++ 类 | 调用开销较大 | 低 | 无 | 调 C 库、快速原型 |
| **cffi** | C 声明 + ABI/API 模式 | 仅 C，无 C++ 类 | 中 | 低 | ABI 模式无需编译 | cryptography、简单 C 库 |
| **SWIG** | 接口文件 `.i` + 代码生成 | C/C++ 都支持，类支持笨重 | 中 | 中高 | 需要 | 老牌项目、多语言绑定 |
| **Boost.Python** | C++ 宏/模板 | 完整 C++，功能强 | 中 | 高（Boost 生态） | 需要，依赖重 | 老一代 C++ 项目 |
| **Cython** | Python 方言 `.pyx` + 可选 C++ | 支持 C++ 类（需声明） | 高 | 中 | 需要 | SciPy 部分模块、数据中心 |
| **pybind11** | 纯 C++ 模板/宏 | **完整现代 C++**，类/继承/STL/异常 | 高 | 中低 | 需要 | PyTorch、TensorFlow、OpenCV、pandas |

### 2.1 pybind11 相对 Boost.Python 的进化

pybind11 出身于 Boost.Python 的作者体系，但做了三件关键减法：

1. **不依赖 Boost**：只需一个头文件目录，`#include <pybind11/pybind11.h>` 即可（header-only）。
2. **用 C++11/14/17 重写核心**：`constexpr`、可变参数模板、完美转发替代了 Boost 的 MPL 重模板。
3. **编译更快、报错更可读**：官方 benchmark（`docs/benchmark.rst`）里，pybind11 的编译时间与二进制体积都明显小于 Boost.Python。

### 2.2 pybind11 相对 Cython 的选择逻辑

- **已有 C++ 代码** → pybind11（不需要重写业务逻辑，直接 `.def()` 暴露）。
- **从零写 Python 加速逻辑，且希望"渐进式"改写** → Cython 更顺（可以只加类型标注）。
- **需要暴露复杂 C++ 类层级、智能指针、虚函数给 Python 继承** → pybind11 明显更自然。
- 两者可以共存：Cython 调用 C++，C++ 内部用 pybind11 暴露给 Python。

### 2.3 一条经验法则

> **接口形态决定工具**：如果对 Python 暴露的是"函数与数据"，ctypes/cffi 够用；
> 如果暴露的是"对象与类型系统"，pybind11 的投入产出比最高。

---

## 第 3 章 原理剖析：pybind11 到底做了什么

这一章解释"为什么写几行 C++ 就能得到一个 Python 模块"。理解了它，后面所有 API 都不会是死记硬背。

### 3.1 一个扩展模块的最小要求（CPython C-API 视角）

Python 导入 `.pyd`/`.so` 时，会寻找一个符号名 `PyInit_<模块名>`，它必须返回 `PyObject*`（一个 `PyModuleDef` 生成的模块对象）。手写 C-API 大概是几十行样板：定义 `PyModuleDef`、实现方法表 `PyMethodDef[]`、解析参数 `PyArg_ParseTuple`、管理引用计数。pybind11 把这套样板全部生成出来。

`PYBIND11_MODULE(HelloWorld, m)` 展开后大致等价于：

```cpp
extern "C" PyObject *PyInit_HelloWorld() {          // 宏参数名 → 初始化函数名
    PyObject *m = ...;                               // 创建/复用模块对象
    // 你的绑定代码写在这里，m 是 py::module_ 引用
    return m;
}
```

**关键结论 1**：模块名必须与 `PYBIND11_MODULE` 的第一个参数一致，也与最终产物文件名一致（去掉 ABI 后缀）。`HelloWorld.cp312-win_amd64.pyd` → `import HelloWorld`。

### 3.2 类型转换器（type caster）：pybind11 的心脏

每当你写 `m.def("add", &add)`，pybind11 都会为签名 `int(int, int)` 实例化一套"转换器"：

```text
Python object ──[type_caster<int>::load]──► C++ int
        ... 调用 add() ...
C++ int ──[type_caster<int>::cast]──► Python object
```

对于 `int`，这是内建转换器；对于 `std::vector<double>`，`..` 提供了"逐元素转换"的容器 caster；对于你自己定义的类，`py::class_<T>` 会注册一个"类型 → Python 类型对象"的映射，转换时走 `type_caster_base<T>`。

**关键结论 2**：pybind11 的"魔法"完全发生在**编译期**——模板实例化把你的 C++ 类型签名翻译成运行期的加载/转换函数指针。因此：

- 每一个"未被支持的类型"会在**编译期**报出很长的模板错误（第 12.2 节教你读懂它们）；
- 运行时开销主要就是"引用计数 + 装箱/拆箱"，没有反射、没有字符串查找。

### 3.3 internals：跨模块共享的全局状态

pybind11 需要全局记录"哪些 C++ 类型已经注册成了哪个 Python 类型"（否则两个模块绑定同一个 C++ 类会得到两个互不兼容的 Python 类）。这些状态保存在一个 `internals` 结构里，通过 Python 的 **capsule（`pybind11_internals_v...`）** 挂在模块上，同进程内的所有 pybind11 模块按 **ABI id / internals 版本**匹配后共享。

由此推出两条工程纪律：

1. **同一进程中的多个扩展模块应使用相同（或 ABI 兼容）的 pybind11 版本**；
2. 触碰 `internals.h` 的结构布局 = ABI 破坏，这也是官方把它列为"一等公民"关注点的原因。

### 3.4 v3 的新分层：smart_holder 与 conduit

pybind11 v3 在所有权与跨框架互操作上做了两项重要扩展（细节见第 10 章）：

- **smart_holder**：让对象能在 `shared_ptr` / `unique_ptr` / Python 所有权之间**安全地传递**，解决 v2 时代 holder 类型一旦选错就"锁死"的问题。v3 中**推荐使用，但为兼容性默认没有打开**。
- **conduit（`pybind11_conduit_v1`）**：一套跨绑定框架/跨 pybind11 版本的稳定协议，让"由不同框架构建的扩展模块之间共享同一个 C++ 对象"成为可能。

### 3.5 头文件地图

pybind11 是 header-only 的，`include/pybind11/` 下的文件就是全部 API。按需 include：

| 头文件 | 提供什么 | 什么时候需要 |
| --- | --- | --- |
| `..` | 模块/函数/类绑定核心 | 永远 |
| `..` | `vector/map/set/optional/...` 自动转换 | 传容器时 |
| `..` | 把容器绑定成"不透明类型" | 需要 in-place 修改大容器时 |
| `..` | `std::function` ↔ Python callable | 接受回调时 |
| `..` | `py::array` / `py::array_t` | 传数组时 |
| `..` | Eigen 矩阵/向量互操作 | 科学计算 |
| `..` | `std::chrono` ↔ `datetime/timedelta` | 时间戳 |
| `..` | `std::complex` ↔ `complex` | 信号处理 |
| `..` | 运算符重载糖 `py::self + py::self` | 值类型 |
| `..` | 嵌入解释器 | C++ 宿主调用 Python |
| `..` | GIL 管理 | 多线程 |
| `..` | 映射到 Python 原生 `enum` | v3 新特性 |
| `..` | 生成 Python 类型注解 | IDE/静态检查友好 |
| `..` | 子解释器 | 隔离运行 |

> 记忆法：**核心一个头，特性一个头**。功能不生效时，先检查是不是忘了包含对应头文件（这是新手第一大坑，见 17 章）。

---

## 第 4 章 环境搭建：Windows + MinGW + Python 3.12 实战

### 4.1 先看清楚本机已有的工具链

本文所有命令都在下面这套环境上实测通过（与你机器上的版本可能不同，但检查方法一致）：

| 组件 | 本机版本 / 路径 | 检查命令 |
| --- | --- | --- |
| 操作系统 | Windows | — |
| Python | 3.12.0，`D:\ruanjian\Python\Python3` | `python --version` |
| C++ 编译器 | MinGW-w64 GCC 16.2.0（ucrt / posix / seh） | `g++ --version` |
| CMake | 4.4.4 | `cmake --version` |
| Ninja | 1.13.2 | `ninja --version` |
| pybind11 | v3.2.0（vendored 于 `..`） | 见 4.2 |
| NumPy | 2.0.0（可选） | `python -c "import numpy; print(numpy.__version__)"` |

一条命令做完环境自检：

```powershell
python --version
g++ --version | Select-Object -First 1
cmake --version  | Select-Object -First 1
ninja --version
python -c "import sys, sysconfig; print(sys.executable); print(sysconfig.get_config_var('EXT_SUFFIX'))"
# 期望输出示例：D:\ruanjian\Python\Python3\python.exe  与  .cp312-win_amd64.pyd
```

最后一行**非常关键**：`EXT_SUFFIX` 决定了你最终产物的文件名，而文件名决定了 Python 能不能 `import` 它。

### 4.2 pybind11 从哪里来：三种取用方式

pybind11 是 **header-only** 库——"库"就是 `include/pybind11/` 下的那些头文件，不需要预先编译任何东西。取用方式有三：

| 方式 | 命令 / 写法 | 适用场景 |
| --- | --- | --- |
| **A. vendored 源码**（本仓库采用） | `git clone` 到 `extern/pybind11`，CMake 里 `add_subdirectory(extern/pybind11)` | 想锁版本、离线、可控；CI 里可复现 |
| **B. pip 安装后 `find_package`** | `pip install pybind11` + `find_package(pybind11 CONFIG REQUIRED)` | 日常开发最省事 |
| **C. 子模块 + Python 工具** | `python -m pybind11 --includes` 手工喂给编译器 | 不用 CMake 的小工程、教学 |

本仓库 `..` 里就是**完整源码树**（`include/`、`docs/`、`tests/`、`tools/`、`..` Python 包）。版本号只有一个权威来源：

```cpp
// pybind11/extern/pybind11/include/pybind11/detail/common.h
#define PYBIND11_VERSION_MAJOR 3
#define PYBIND11_VERSION_MINOR 2
#define PYBIND11_VERSION_MICRO 0
#define PYBIND11_VERSION_PATCH 0a0     // → 3.2.0a0
```

> 小实验：`Set-Content` 改一下 `common.h` 里的版本号，再重新配置 CMake，你会看到 `-- pybind11 v3.2.0` 那行输出随之变化。这是验证"你正在编译的到底是哪份 pybind11"的最快方式。

### 4.3 一个隐蔽的"命名空间包"陷阱

本仓库根目录下有一个**叫 `pybind11` 的目录**（就是示例工程目录），它里面**没有 `__init__.py`**。Python 3 会把它当作 *namespace package*，从而**遮蔽**真正安装的 pybind11 包：

```text
PS> cd D:\study\programming\python\project\Quantify
PS> python -c "import pybind11; print(pybind11.__file__)"
None                                   # ← 被遮蔽了，__file__ 为 None

PS> python -m pybind11 --version
python.exe: No module named pybind11.__main__; 'pybind11' is a package and cannot be directly executed
```

**结论**：
- 在仓库根目录下，不要指望 `python -m pybind11` 能工作；
- 使用 vendored 路线（方式 A）时根本不需要它——CMake 的 `add_subdirectory` 已经拿到一切；
- 真要用方式 C，请先 `cd` 到别的目录，或把 `PYTHONPATH` 指向真正的包目录。

### 4.4 本机实测过的三个 Windows + MinGW 硬性要求

如果你在 Windows 上用 MinGW 手工编译（不走 CMake），下面三条**缺一不可**：

```powershell
$py  = 'D:\ruanjian\Python\Python3'
$pyb = 'D:\study\programming\python\project\Quantify\pybind11\extern\pybind11'
$sfx = & "$py\python.exe" -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))"

& 'D:\study\MinGW\mingw64\bin\g++.exe' -O3 -Wall -shared -std=c++17 -fPIC -static `
  -I "$py\Include" -I "$pyb\include" `
  hello.cpp -o "HelloWorld$sfx" `
  -L "$py\libs" -lpython312
```

1. **`-static`（不只是 `-static-libgcc -static-libstdc++`）**
   少了它，链接能成功，但 `import` 时报 `ImportError: DLL load failed`——因为 `libwinpthread-1.dll` 不在依赖搜索路径里。用 `objdump -p HelloWorld*.pyd | Select-String 'DLL Name'` 可以立刻看到缺口。
2. **必须显式 `-L "$py\libs" -lpython312`**
   否则 `ld.exe: undefined reference to '__imp_PyLong_Type'` 一片。注意这与 Linux 相反（第 6.6 节）。
3. **`-I "$py\Include"`**
   否则 `fatal error: Python.h: No such file or directory`。

另外两个实测事实：

- 这台 Python 3.12 的 `sysconfig` 里**没有 `SOABI` 键**（`get_config_var('SOABI')` 返回 `None`），但 `EXT_SUFFIX` 是 `.cp312-win_amd64.pyd`。CMake 侧的 pybind11 正是靠直接问解释器要 `EXT_SUFFIX` 才拼出正确文件名。
- **pybind11 不支持 `Py_LIMITED_API` / Stable ABI**：加上 `-DPy_LIMITED_API=0x030C0000` 会立即编译失败（`error: 'PyGILState_Check' was not declared in this scope`）。想覆盖多个 Python 小版本，只能每个版本各出一个 wheel（详见 6.5、15.4）。

### 4.5 强烈建议：用虚拟环境

扩展模块与 Python 版本/ABI 强绑定，多项目共用系统 Python 极易互相污染：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install numpy pybind11 pytest scikit-build-core
```

CMake 一定要找到**你正在使用的那个解释器**，否则会出现"编出来的 `.pyd` 装不进当前环境"的诡异现象：

```powershell
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release `
      -DPython_EXECUTABLE="$PWD\.venv\Scripts\python.exe"
```

> 注意：v3.0 起 **`PYTHON_EXECUTABLE` 这类旧变量已失效**，请使用 `Python_EXECUTABLE` / `Python_ROOT_DIR`，并加上 `set(PYBIND11_FINDPYTHON ON)`（详见 6.4）。

---

## 第 5 章 第一个扩展逐行解剖

### 5.1 绑定源文件

```cpp
#include <pybind11/pybind11.h>        // ① 唯一的必需头文件，内部会 include <Python.h>

int add(int i, int j) {               // ② 要被暴露的普通 C++ 函数
    return i + j;
}

PYBIND11_MODULE(HelloWorld, m) {      // ③ 模块定义宏：模块名 + 绑定上下文变量名
    m.doc() = "pybind11 example plugin"; // ④ 可选：写入模块 __doc__

    m.def("add", &add, "A function that adds two numbers"); // ⑤ 绑定一个函数
}
```

逐条说明：

**① 头文件顺序**
`..` 必须**第一个**被 include（它会 include `<Python.h>`，而 `Python.h` 对 include 顺序敏感）。工程里应把它放在最前面，或者用预编译头统一引入。

**② 只写普通 C++**
`add` 里没有任何 pybind11 代码，这正是 pybind11 的核心价值：**业务代码零侵入**，绑定层单独写。

**③ `PYBIND11_MODULE(name, m)` 的三条铁律**

1. 第一个参数是模块名，**不加引号**；它同时决定导出的初始化符号 `PyInit_<name>`，因此必须与**最终产物文件名**（去掉 `.cp312-win_amd64.pyd` 之类的后缀）一致——否则就是经典的
   `ImportError: dynamic module does not define module export function (PyInit_HelloWorld)`。
2. 第二个参数是**变量名**，宏内部把它声明为 `py::module_ &` 形参（这里叫 `m`，你也可以叫 `mod`）。
3. **它后面必须直接跟 `{ ... }` 函数体**，不能在宏参数位置写 lambda。要绑定的 lambda 写在函数体内部的 `m.def(...)` 里。

`PYBIND11_MODULE` 生成的是 **PEP 489 multi-phase init** 模块。一个重要推论：**模块初始化函数会为每个 import 它的（子）解释器各执行一次，且可能并发**。因此模块初始化代码里不要写"只应执行一次"的全局副作用；确实需要"只初始化一次"的 Python 对象时，用 `py::gil_safe_call_once_and_store`（见 `..`），不要用裸 `static`——后者与 GIL 会形成相反的锁序，可能死锁。

`PYBIND11_MODULE` 还接受可选的"能力声明"标签（v3 常用）：

```cpp
PYBIND11_MODULE(example, m, py::mod_gil_not_used()) {
    // 承诺：本模块的 C++ 代码线程安全，可在 free-threaded（no-GIL）Python 3.13+ 下使用
}

PYBIND11_MODULE(example, m,
                py::multiple_interpreters::per_interpreter_gil(), // 支持隔离子解释器
                py::mod_gil_not_used()) {
}
```

| tag | 含义 |
| --- | --- |
| `py::mod_gil_used()` | 默认值：模块依赖 GIL |
| `py::mod_gil_not_used()` | 模块线程安全，可运行在 no-GIL 构建上（**这是承诺**，写错会崩） |
| `py::multiple_interpreters::per_interpreter_gil()` | 支持 3.12+ 隔离子解释器（各有独立 GIL） |
| `py::multiple_interpreters::shared_gil()` | 只支持共享 GIL 的 legacy 子解释器 |
| `py::multiple_interpreters::not_supported()` | 显式不支持（默认） |

**④ `m.doc()`**
写入模块的 `__doc__`。`m` 是 `py::module_`，于是你也可以直接挂属性：

```cpp
m.attr("__version__") = "1.0.0";      // 社区约定：版本号
m.attr("the_answer") = 42;            // 内建类型自动转换
py::module_ sub = m.def_submodule("sub", "A submodule");  // 子模块，可递归嵌套
```

**⑤ `m.def(name, func, ...)` 的参数形态**

```cpp
template <typename Func, typename... Extra>
module_ &def(const char *name_, Func &&f, const Extra &...extra);
```

- 第 1 个参数：Python 侧名字（重复调用同名 → 自动组成**重载链**）。
- 第 2 个参数：函数指针 / 成员函数指针 / lambda / `std::function` / `py::cpp_function`。
- 其余参数是**位置自由的标签**：docstring（`const char*`）、`py::arg("i")`、默认值、返回策略、`py::keep_alive<...>`、`py::call_guard<...>` 等，顺序随意。

### 5.2 CMake 脚本

```cmake
cmake_minimum_required(VERSION 3.23)
project(HelloWorld)

add_subdirectory(extern/pybind11)          # 把 vendored 的 pybind11 拉进来
pybind11_add_module(HelloWorld hello.cpp)  # 一行生成扩展模块目标
```

原文件里还有几行值得点评：

```cmake
set(CMAKE_CXX_STANDARD 17)          # ✅ 现代 C++，推荐 17 起
set(CMAKE_CXX_STANDARD_REQUIRED ON) # ✅ 编译器不支持就报错，别悄悄降级
set(CMAKE_CXX_EXTENSIONS OFF)       # ✅ 用标准 C++，不用 gnu++17

if(MINGW)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -static")   # ✅ 消除 libwinpthread 依赖
elseif(MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")  # ✅ 静态运行库
endif()
```

而这两行：

```cmake
set(PYTHON_EXECUTABLE "")
set(PYTHON_INCLUDE_DIRECTORY "")
```

**建议删掉**。原因：v3.0 起 pybind11 的 CMake 默认走现代 `FindPython`，`PYTHON_*` 这套旧变量已不再影响构建；`PYTHON_INCLUDE_DIRECTORY` 更是从来就不是 pybind11 的变量名。想指定解释器请用 `Python_EXECUTABLE`。

另外一个小细节：本仓库的配置文件名是 `CMakelists.txt`（小写 `l`）。Windows 的 NTFS 不区分大小写所以能正常工作，但 **Linux/macOS 上 CMake 只认 `CMakeLists.txt`**，会直接报"找不到 CMakeLists.txt"。养成正确大小写的习惯。

### 5.3 构建与运行

```powershell
cd D:\study\programming\python\project\Quantify\pybind11
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DPYBIND11_FINDPYTHON=ON
cmake --build build

# 产物
Get-ChildItem build\HelloWorld*.pyd
# HelloWorld.cp312-win_amd64.pyd

# 导入验证（CWD 必须是 .pyd 所在目录，或把 build 加进 PYTHONPATH）
cd build
python -c "import HelloWorld; print(HelloWorld.add(1, 2))"
# 3
```

**为什么总用 `-S`/`-B`？** 因为 `cmake ..` 的结果取决于你此刻站在哪——`log.txt` 里那次报错就是这么来的（第 13.1 节会复盘）。

Python 侧的调用（`main.py`）：

```python
import HelloWorld as hw

print(hw.add(1, 2))   # 3
```

`main.py` 与 `.pyd` 的相对位置决定了能否 import：

| 布局 | 能否 `import HelloWorld` |
| --- | --- |
| `main.py` 与 `.pyd` 同目录 | ✅ |
| `main.py` 在源码目录，`.pyd` 在 `build/` | ❌（除非 `sys.path`/`PYTHONPATH` 指向 `build/`） |
| `.pyd` 放进 Python 的 `site-packages/` | ✅ |

临时方案：

```powershell
$env:PYTHONPATH = 'D:\study\programming\python\project\Quantify\pybind11\build'
python main.py
```

### 5.4 检查成果：`__doc__` 里藏着 v3 的新特性

在我本机实测：

```text
>>> import HelloWorld as hw
>>> print(hw.__doc__)
pybind11 example plugin
>>> print(hw.add.__doc__)
add(arg0: typing.SupportsInt | typing.SupportsIndex, arg1: typing.SupportsInt | typing.SupportsIndex) -> int

A function that adds two numbers
>>> hw.add(1, 2)
3
```

注意 `add(...)` 那一行：**pybind11 v3 会自动为绑定函数生成 Python 类型注解**，直接呈现在 `__doc__` 里。这对 IDE 补全、`help()`、静态检查都有价值。参数名来自 `py::arg()`，所以只要写好命名参数，签名就好看：

```cpp
m.def("add", &add, "两数相加", py::arg("i"), py::arg("j"));
// → add(i: ..., j: ...) -> int
```

更进一步，用 `..` 可以生成 `list[str]`、`Callable[[int], float]` 这类泛型注解（第 9.6 节）。

### 5.5 "第一个模块"验收清单

```text
[ ] PYBIND11_MODULE 的第一个参数 == 目标名 == 产物文件名（去掉 ABI 后缀）
[ ] 编译无 warning 级别的 Python.h / ABI 不匹配提示
[ ] 用目标解释器 python -c "import <mod>" 成功
[ ] __doc__ 与函数签名可读（写了 py::arg / docstring）
[ ] Release 构建（-DCMAKE_BUILD_TYPE=Release），不是默认空配置
[ ] 没有把 build/ 产物提交进版本库
```

---

## 第 6 章 构建系统详解：CMake 与四条集成路线

### 6.1 路线 A：pip 安装 + `find_package`（日常推荐）

```powershell
python -m pip install pybind11
python -m pybind11 --cmakedir      # 打印 pybind11Config.cmake 所在目录
```

```cmake
cmake_minimum_required(VERSION 3.15...4.2)
project(example LANGUAGES CXX)

set(PYBIND11_FINDPYTHON ON)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(example example.cpp)
install(TARGETS example DESTINATION .)
```

```powershell
$cmakedir = python -m pybind11 --cmakedir
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -Dpybind11_ROOT=$cmakedir
cmake --build build
```

若想让**系统级** `find_package(pybind11)` 找到它（不推荐在系统 Python 上这么干，虚拟环境里可以）：

```powershell
python -m pip install "pybind11[global]"   # 装到 <env>/include/pybind11 与 <env>/share/cmake/pybind11
```

### 6.2 路线 B：vendored `add_subdirectory`（本仓库采用）

```cmake
cmake_minimum_required(VERSION 3.15...4.2)
project(HelloWorld LANGUAGES CXX)

set(PYBIND11_FINDPYTHON ON)          # 消除 "Using compatibility mode for Python" 警告
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_subdirectory(extern/pybind11)    # ← 与 find_package 提供的接口功能完全一致
pybind11_add_module(HelloWorld hello.cpp)
```

`add_subdirectory` 模式的两个副作用（源码里确认过）：

- `PYBIND11_FINDPYTHON` 默认变成 `COMPAT`（配置期那条兼容模式警告就来自这里）；
- pybind11 头文件按 **SYSTEM** 头处理（屏蔽其自身警告），并同时设置好旧变量 `pybind11_INCLUDE_DIR`。

### 6.3 路线 C：不用 CMake，手工编译

```bash
# Linux
c++ -O3 -Wall -shared -std=c++17 -fPIC \
    $(python3 -m pybind11-study --includes) example.cpp \
    -o example$(python3-config --extension-suffix)
```

```bash
# macOS：必须加 -undefined dynamic_lookup
c++ -O3 -Wall -shared -std=c++17 -undefined dynamic_lookup \
    $(python3 -m pybind11-study --includes) example.cpp \
    -o example$(python3-config --extension-suffix)
```

```powershell
# Windows / MinGW（本机实测可用）
$py  = 'D:\ruanjian\Python\Python3'
$pyb = 'D:\study\programming\python\project\Quantify\pybind11\extern\pybind11'
$sfx = & "$py\python.exe" -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))"
& 'D:\study\MinGW\mingw64\bin\g++.exe' -O3 -Wall -shared -std=c++17 -fPIC -static `
  -I "$py\Include" -I "$pyb\include" hello.cpp -o "HelloWorld$sfx" `
  -L "$py\libs" -lpython312
```

`python -m pybind11` 提供的工具开关：

| 开关 | 输出 | 备注 |
| --- | --- | --- |
| `--includes` | `-I<python include> -I<pybind11 include>` | 未加引号，路径含空格时不能简单 split |
| `--extension-suffix` | `.cp312-win_amd64.pyd` | 直接问解释器要 `EXT_SUFFIX` |
| `--version` | `3.2.0a0` | 需能 import 到 pybind11 包 |
| `--cmakedir` | CMake 配置目录 | **在源码树模式下必然失败**（包未安装） |
| `--srcdir` | 预编译用的 `src/` 目录 | v3.2 预编译模式用 |
| `--cflags` / `--ldflags` / `--file=` | v3.2 新增的一键编译辅助 | 基于 `python-config`，**不支持 MSVC/Windows-MinGW** |

### 6.4 `pybind11_add_module` 全解

```cmake
pybind11_add_module(<name> [MODULE | SHARED] [EXCLUDE_FROM_ALL]
                    [NO_EXTRAS] [THIN_LTO] [OPT_SIZE] [PRECOMPILE | NO_PRECOMPILE]
                    source1 [source2 ...])
```

| 选项 | 行为 | 注意 |
| --- | --- | --- |
| （省略） | 默认 `MODULE` | 只给 Python 导入用 |
| `MODULE` / `SHARED` | `SHARED` 生成普通动态库，可被其他目标链接 | 新模式 `SHARED`/`STATIC` 会链 `pybind11::embed` |
| `EXCLUDE_FROM_ALL` | 不加入默认构建 | — |
| `NO_EXTRAS` | 关闭 LTO、strip、`/MP`、`OPT_SIZE` | **关不掉 `-fvisibility=hidden`**（v2.2 起无法 opt-out） |
| `THIN_LTO` | 优先 `-flto=thin` | 若已定义 `CMAKE_INTERPROCEDURAL_OPTIMIZATION` 则被忽略 |
| `OPT_SIZE` | `/Os` 或 `-Os`（仅 Release/MinSizeRel/RelWithDebInfo） | 官方实测约减 25% 体积 |
| `PRECOMPILE` | 创建并链接 `pybind11::precompiled` 静态库（v3.2 新特性） | 显著缩短多 TU 编译时间，见 6.7 |
| `NO_PRECOMPILE` | 全局开预编译时，本目标退出 | — |
| `WITHOUT_SOABI` / `WITH_SOABI` | 控制文件名后缀处理 | 仅新模式（FindPython） |

配置期可用的 pybind11 选项（`extern/pybind11/CMakeLists.txt`）：`PYBIND11_TEST`、`PYBIND11_INSTALL`、`PYBIND11_NOPYTHON`、`PYBIND11_FINDPYTHON`、`PYBIND11_SIMPLE_GIL_MANAGEMENT`、`PYBIND11_USE_CROSSCOMPILING`、`PYBIND11_INTERNALS_VERSION` 等。

**接口 target 速查**（手工组装时用）：

| target | 用途 |
| --- | --- |
| `pybind11::headers` | 只要头文件路径（与 Python 无关的编译单元可用） |
| `pybind11::pybind11` | 头文件 + Python 头文件 |
| `pybind11::module` | 扩展模块全量（`pybind11::pybind11` + Python 模块链接）；**只用它时要自己设 `CMAKE_CXX_VISIBILITY_PRESET hidden`** |
| `pybind11::embed` | 嵌入解释器（`Python::Python`） |
| `pybind11::lto` / `pybind11::thin_lto` | LTO 旗标（Debug/RelWithDebInfo 不生效；MinGW 恒禁用） |
| `pybind11::windows_extras` | MSVC 的 `/bigobj`、`/MP`（绑定代码必加 `/bigobj`） |
| `pybind11::opt_size` | `/Os` / `-Os` |
| `pybind11::python_link_helper` | Apple 平台加 `-undefined dynamic_lookup` |

手工组装版（等价于 `pybind11_add_module`）：

```cmake
add_library(example MODULE main.cpp)
target_link_libraries(example PRIVATE
    pybind11::module pybind11::lto pybind11::windows_extras
    pybind11::opt_size)
pybind11_extension(example)
if(NOT MSVC AND NOT ${CMAKE_BUILD_TYPE} MATCHES Debug|RelWithDebInfo)
    pybind11_strip(example)
endif()
set_target_properties(example PROPERTIES CXX_VISIBILITY_PRESET "hidden")
```

### 6.5 第四条路线：Python 打包工具链

**(a) setuptools + `pybind11.setup_helpers`**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools", "pybind11"]
build-backend = "setuptools.build_meta"
```

```python
# setup.py
from glob import glob
from setuptools import setup
from pybind11_study.setup_helpers import Pybind11Extension, build_ext, ParallelCompile

ParallelCompile("NPM_BUILD_JOBS", default=0, max=8).install()

ext_modules = [
   Pybind11Extension("python_example", sorted(glob("src/*.cpp")), cxx_std=17),
]

setup(name="python_example", version="0.1.0",
      ext_modules=ext_modules, cmdclass={"build_ext": build_ext})
```

`Pybind11Extension` 会自动补：Windows `/EHsc /bigobj`；非 Windows `-fvisibility=hidden -g0`；macOS `stdlib=libc++` 与 deployment target。

**(b) scikit-build-core（现代推荐）**——pybind11 官方自己就用它：

```toml
[build-system]
requires = ["scikit-build-core", "pybind11"]
build-backend = "scikit_build_core.build"

[project]
name = "example"
version = "0.1.0"
```

```cmake
# CMakeLists.txt
find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(example example.cpp)
install(TARGETS example DESTINATION .)
```

```powershell
python -m pip install build
python -m build            # 先 sdist 再 wheel（sdist 缺 C++ 源码会立刻暴露）
```

### 6.6 ABI、文件名与"一个 pyd 能跨几个 Python 版本"

**文件名从哪来？** `pybind11_extension(target)` 只做三件事：

```cmake
PREFIX        ""                                  # 无前缀（不是 lib 开头）
DEBUG_POSTFIX "${PYTHON_MODULE_DEBUG_POSTFIX}"    # Debug 解释器用
SUFFIX        "${PYTHON_MODULE_EXTENSION}"        # 本机 = .cp312-win_amd64.pyd
```

后缀的取值优先级：有解释器时直接问它要 `EXT_SUFFIX`；交叉编译（无解释器）时依次尝试 `SETUPTOOLS_EXT_SUFFIX` → `SKBUILD_SOABI` → `Python_SOABI`，都拿不到就 `FATAL_ERROR` 并要你手工设 `PYTHON_MODULE_EXTENSION`。

**兼容性矩阵（务必记住）**：

| 维度 | 能否跨 | 原因 |
| --- | --- | --- |
| 同一 CPython 小版本的补丁版（3.12.0 ↔ 3.12.10） | ✅ | 正是 `cp312` 标签的含义 |
| 跨 CPython 小版本（3.12 ↔ 3.13） | ❌ | 文件名与内部结构都变 |
| 跨实现（CPython ↔ PyPy ↔ GraalPy） | ❌ | 各需单独构建 |
| GIL 版 ↔ free-threaded（3.13t） | ❌ | `Py_GIL_DISABLED` 改变 ABI |
| Release ↔ Debug Python | ❌ | `Py_DEBUG` / `_d` 后缀 |
| **abi3 / Stable ABI（跨小版本）** | ❌ | **pybind11 不支持**，实测 `Py_LIMITED_API` 一开就编译失败 |

```text
example-0.1.0-cp312-cp312-win_amd64.whl              # 本机形态
example-0.1.0-cp311-cp311-manylinux_2_17_x86_64.whl
example-0.1.0-cp39-abi3-win_amd64.whl                # ← abi3，pybind11 产不出来
```

所以发布多版本支持的唯一正道是 **cibuildwheel**（每个 CPython 小版本各出一个 wheel）：

```powershell
python -m pip install cibuildwheel
$env:CIBW_BUILD = 'cp312-*'
cibuildwheel --output-dir wheelhouse
```

### 6.7 编译期与运行期优化

**(1) v3.2 的预编译模式（对"编译慢"最有效）**

```cmake
pybind11_add_module(example PRECOMPILE example.cpp)   # 第一个 PRECOMPILE 目标创建静态库
set(PYBIND11_PRECOMPILE ON)                           # 或全局默认
pybind11_add_module(other NO_PRECOMPILE other.cpp)    # 单目标退出
```

原理：把 pybind11 的非模板实现部分（`src/*.cpp`）**每个 build tree 只编译一次**，而不是每个翻译单元重复实例化。代价与约束：

- 库与所有链接它的模块必须在 `PYBIND11_INTERNALS_VERSION`、`Py_GIL_DISABLED`、`PYBIND11_SIMPLE_GIL_MANAGEMENT`、`PYBIND11_DETAILED_ERROR_MESSAGES` 等宏上一致，否则链接期给出可读的 `pybind11_precompiled_config` 未定义符号；
- 预编译库**不带 LTO**，Release 下空函数最坏约 +10%（可手动 `set_target_properties(pybind11_precompiled PROPERTIES INTERPROCEDURAL_OPTIMIZATION ON)`）；
- 与 `PYBIND11_NOPYTHON` 不兼容。

**(2) 拆分翻译单元**

```cpp
// example.cpp 只做汇总
void init_basic(py::module_ &);
void init_quant(py::module_ &);

PYBIND11_MODULE(example, m, py::mod_gil_not_used()) {
    init_basic(m);
    init_quant(m);
}
```

收益：单 TU 内存下降、可并行编译、增量构建快。这是官方测试套件采用的组织方式。

**(3) LTO / strip / 可见性**

- LTO 默认开，但 `Debug`/`RelWithDebInfo` 永不启用，**MinGW 被硬编码禁用**（就是 log.txt 里那两行提示）；
- 一旦你定义了 `CMAKE_INTERPROCEDURAL_OPTIMIZATION`（哪怕设成 `OFF`），pybind11 的自动探测就完全让路；
- `-fvisibility=hidden` 无法关闭（v2.2 起），它是多模块共存与体积优化的基石；只与 `pybind11::module` 链接时记得自己设 `CMAKE_CXX_VISIBILITY_PRESET hidden`；
- `OPT_SIZE` 实测可减约 25% 体积，可按目标开启；
- 编译报 `recursive template instantiation exceeded maximum depth of 256` → 加 `-ftemplate-depth=1024`。

**(4) 别忘了这些"不要"**

- 不要加 `-fno-exceptions` / `-fno-rtti`（类型转换、holder、trampoline 依赖它们）；
- 不要链 `-lpython`（Linux/macOS 上不链是**正确**做法，扩展在进程内解析符号）；
- 不要在 Windows 混用 `/MT` 与 `/MD`、混用 MinGW 与 MSVC 二进制。

### 6.8 跨平台要点速查

```cmake
# MSVC：源码含中文必须 /utf-8；模板多必须 /bigobj
target_compile_options(mymod PRIVATE /utf-8)
target_link_libraries(mymod PRIVATE pybind11::windows_extras)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
```

```cmake
# MinGW：静态链接，消除 libwinpthread/libstdc++/libgcc 的 DLL 依赖
if(MINGW)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -static")
endif()
```

```bash
# macOS universal2
cmake -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64" ..
```

```bash
# Linux：manylinux 镜像里没有 libpython 开发库 → CMake 用 Development.Module
# wheel 外部依赖交给 auditwheel；cibuildwheel 会自动调用
auditwheel repair dist/*.whl
```

### 6.9 打包分发的几个注意事项

```powershell
python -m build --wheel                 # 生成 dist/example-0.1.0-cp312-cp312-win_amd64.whl
python -m pip install dist\*.whl
python -c "import example; print(example.add(1, 2))"
```

要点：

- **SDist 必须包含 C++ 源码与 CMake 配置**（`MANIFEST.in` 写 `recursive-include src *.cpp *.h`、`include CMakeLists.txt`），`python -m build` 的两步流程能帮你提前暴露缺失；
- **`package_data` 不是给扩展模块用的**——`ext_modules` 里的 `.pyd` 由 `build_ext` 负责安装；
- 改了 C++ 代码但没改版本号，`pip install .` 可能命中缓存 → 用 `--no-cache-dir`、`pip install -e .` 或 `setuptools_scm`；
- 其他生态入口：`conda install -c conda-forge pybind11`、`vcpkg install pybind11`、Conan、`pybind11.pc`（pkg-config）。

---

## 第 7 章 函数绑定全解

### 7.1 `m.def` 的参数模型

```cpp
template <typename Func, typename... Extra>
module_ &def(const char *name_, Func &&f, const Extra &...extra);
```

- **`name_`**：Python 侧名字。**同名重复 `.def` 会自动组成重载链**。
- **`f`**：函数指针 / 成员函数指针 / lambda / `std::function` / `py::cpp_function`。
- **`extra...`**：位置自由的标签集合，见下表。

| 标签 | 作用 |
| --- | --- |
| `py::arg("i")` | 命名参数：支持关键字调用，并进入签名文档 |
| `py::arg("i") = 3` / `"i"_a = 3` | 默认值 |
| `py::arg_v("i", T(3), "T(3)")` | 默认值 + 自定义签名的显示文本（对象没有好 `__repr__` 时用） |
| `py::kw_only()` | 之后的参数只能按关键字传（对应 Python 的 `*`） |
| `py::pos_only()` | 之前的参数只能按位置传（对应 Python 的 `/`） |
| `py::arg("x").noconvert()` | 该参数禁止隐式转换 |
| `py::arg("x").none(true/false)` | 是否允许 `None` |
| `py::is_operator()` | 声明这是运算符实现：参数不匹配返回 `NotImplemented` 而不是抛 `TypeError` |
| `py::return_value_policy::*` | 返回值策略 |
| `py::keep_alive<Nurse, Patient>()` | 生命周期策略 |
| `py::call_guard<T>()` | 调用前后的 RAII 守卫（最常用于释放 GIL） |
| `py::prepend()` | 把该重载插到链首 |

> 注意：**没有 `py::noconvert()` 这个独立标签**，只有 `py::arg(...).noconvert()`（或 `py::arg().noconvert()`）。

### 7.2 命名参数、默认值、仅关键字参数

```cpp
using namespace pybind11::literals;   // 启用 "name"_a 字面量

m.def("add", &add, "两数相加", "i"_a, "j"_a);
m.def("greet", &greet, "打招呼", py::arg("name"), py::arg("prefix") = "Hello");

// 仅关键字参数（symbol 之后必须用关键字）
m.def("make_order",
      [](const std::string &symbol, int qty) { return symbol + " x" + std::to_string(qty); },
      py::arg("symbol"), py::kw_only(), py::arg("qty") = 100);

// 可变参数
m.def("portfolio_value", [](py::kwargs kwargs) {
    py::dict d(kwargs);
    double cash = d.contains("cash") ? py::cast<double>(d["cash"]) : 0.0;
    return cash;
});
```

Python 侧效果：

```python
greet("world")                       # 'Hello, world!'
greet("world", prefix="Hi")          # 'Hi, world!'
make_order("AAPL", qty=200)          # 'AAPL x200'
make_order("AAPL", 200)              # TypeError：qty 必须用关键字
```

**默认参数无法自动推导**——C++ 的默认值不属于函数类型信息，必须显式写。默认值在**模块初始化时**就被转换成 Python 对象，因此它引用的类型必须已经注册。

几条实用规矩：

- 只要给某个参数写了 `py::arg` 选项，就要给**所有**参数各写一个（哪怕写成 `py::arg()`），否则参数个数对不上；
- `py::kwargs` 必须是最后一个参数，且**不要**再配 `py::arg`；
- `py::args` 之后的参数自动变成 keyword-only。

### 7.3 重载与重载解析

```cpp
int combine(int a, int b);
std::string combine(const std::string &a, const std::string &b);

// 用 py::overload_cast 消除歧义（C++14 起）
m.def("combine", py::overload_cast<int, int>(&combine), "整数相加");
m.def("combine", py::overload_cast<const std::string &, const std::string &>(&combine), "字符串拼接");
```

解析规则（**理解它就能解释 90% 的"为什么没进我期望的重载"**）：

1. **两遍扫描**：第一遍要求所有参数都**不需要隐式转换**；全部失败才进入第二遍（允许转换，但显式标了 `noconvert` 的参数仍不允许），仍失败则抛 `TypeError`。
2. 每遍内部按**注册顺序**尝试；`py::prepend()` 可把某个重载提到链首。
3. 不会按"需要转换的参数个数"细化排序——先 0 转换、再按注册顺序。

成员函数重载还可以按 `const` 区分：

```cpp
.def("foo_mutable", py::overload_cast<int, float>(&Widget::foo))
.def("foo_const",   py::overload_cast<int, float>(&Widget::foo, py::const_))
```

### 7.4 lambda、成员函数与 `std::function` 回调

```cpp
#include <pybind11/functional.h>

// Python 函数 -> std::function
std::vector<double> apply(const std::vector<double> &xs, const std::function<double(double)> &f);
m.def("apply", &apply, "逐元素应用 Python 回调", "xs"_a, "f"_a);
```

```python
example.apply([1.0, 2.0], lambda x: x * 10)   # [10.0, 20.0]
```

要点：lambda 会被**拷贝存储**，所以必须可拷贝构造；`std::function` 回调有一个"无状态快路径"——如果传进来的是 pybind11 绑定的无状态函数且签名匹配，pybind11 直接抽取底层 C++ 函数指针，**完全避免 C++→Python→C++ 的往返开销**。

### 7.5 返回值策略：七个值，请背下来

| 策略 | 语义 | 什么时候用 |
| --- | --- | --- |
| `automatic`（默认） | 指针 → `take_ownership`；右值引用 → `move`；左值引用 → `copy` | 默认，适合大多数返回值 |
| `automatic_reference` | 同上，但指针 → `reference` | C++ 调 Python 函数、`stl.h` caster 的默认 |
| `take_ownership` | 接管所有权，Python 引用归零时 `delete` | 工厂返回 `new T` |
| `copy` | 复制一份给 Python | 返回成员/大对象但要解耦 |
| `move` | `std::move` 进新对象 | 返回局部/临时 |
| `reference` | 只引用，不接管 | 全局/静态/单例对象 |
| `reference_internal` | 引用 + 用 `keep_alive<0,1>` 钉住父对象 | 返回成员引用；**属性 getter 的默认策略** |

> ⚠️ **不存在 `return_value_policy::none`**。想返回 `None` 请用 `py::none()`、返回 `void`、或返回 `std::optional`/`std::nullopt`。

官方给出的"会炸"的例子：

```cpp
Data *get_data() { return _data; }   // 指向静态数据
m.def("get_data", &get_data);        // ← 默认 automatic 会 take_ownership，Python 去 delete 它 → 崩溃
m.def("get_data", &get_data, py::return_value_policy::reference);   // ✅
```

三条补充：

- 策略**只对 pybind11 没见过的实例生效**（同类型同地址会直接复用已有包装对象）；
- 返回**智能指针**时无需指定策略；
- `reference_internal` 有个容易忽略的细节：**返回值不是左值引用或指针时会静默退化成 `move`**（v3 行为）。

### 7.6 `keep_alive`：索引从 1 开始，0 表示返回值

```cpp
py::class_<Child>(m, "Child")
    .def(py::init<Parent &>(), "parent"_a, py::keep_alive<1, 2>())  // 1 = self，2 = 第一个实参
    .def("parent", &Child::parent, py::return_value_policy::reference_internal);
```

语义：**第 2 个参数（Patient）至少活到第 1 个参数（Nurse）被回收**，索引 0 表示返回值，方法里 1 是隐式 `this`，普通实参从 2 开始。索引写错会在运行期得到：

```text
RuntimeError: Could not activate keep_alive!
```

我的实测结果：`Child(parent)` 之后 `del parent`，甚至 `gc.collect()`，`child.parent()` 依然可用——这就是 `keep_alive` 在起作用。

### 7.7 `call_guard`：一行释放 GIL

```cpp
double busy_sum(std::size_t n);
double busy_sum_releasing_gil(std::size_t n);

m.def("busy_sum_releasing_gil", &busy_sum_releasing_gil, py::call_guard<py::gil_scoped_release>());
```

等价于在函数体开头放一个 `py::gil_scoped_release` 对象。细节：

- `T` 只需**默认可构造**；多个守卫写 `py::call_guard<T1, T2>()`，构造从左到右、析构逆序；
- **参数转换发生在守卫构造之前**，**返回值转换发生在守卫析构之后**——也就是说释放区间不覆盖跨语言转换；
- 因为守卫要默认构造，**无法**通过 `call_guard` 传 `gil_scoped_release(bool disassoc)` 的参数。

### 7.8 文档字符串与类型注解（v3 的加分项）

```cpp
m.def("add", &add, "两数相加", "i"_a, "j"_a);
```

实测 `__doc__`：

```text
add(i: typing.SupportsInt | typing.SupportsIndex, j: typing.SupportsInt | typing.SupportsIndex) -> int

两数相加
```

v3 会自动生成这样的签名。想让容器类型也好看，用 `..`：

```cpp
#include <pybind11/typing.h>

m.def("pass_list_of_str", [](py::typing::List<py::str> arg) {
    // 用法与 py::list 完全一致
});
// → pass_list_of_str(arg0: list[str]) -> None
```

多行 docstring 用原始字符串，注意**不要用 TAB**、各行缩进保持一致：

```cpp
m.def("foo", &foo, R"doc(
    The foo function

    Parameters
    ----------
)doc");
```

---

## 第 8 章 类与对象绑定全解

### 8.1 `py::class_` 的模板参数

```cpp
py::class_<Pet>(m, "Pet");                                       // 默认 holder = std::unique_ptr<Pet>
py::class_<Dog, Pet>(m, "Dog");                                  // 声明基类（"箭头表示法"）
py::class_<Account, std::shared_ptr<Account>>(m, "Account");     // 指定 holder
py::class_<Animal, PyAnimal, py::smart_holder>(m, "Animal");     // v3 推荐：smart_holder
```

- 第一个模板参数是被绑定的类型，**其余参数（基类 / holder / trampoline）顺序任意**，pybind11 自动识别；
- **一个类型及其派生类只能有一个 holder 类型**，选错了会出现"编译能过、运行期段错误"；
- v3 新增简写 `py::classh<T>` ≡ `py::class_<T, py::smart_holder>`，字符数相同，便于整体替换试验。

类级标签（作为 `class_` 的额外参数）：`py::dynamic_attr()`、`py::buffer_protocol()`、`py::multiple_inheritance()`、`py::module_local()`、`py::is_final()`、`py::metaclass(...)`、`py::custom_type_setup(...)`。

### 8.2 构造：`py::init` 与工厂

```cpp
struct Price { explicit Price(double v); };

py::class_<Price>(m, "Price")
    .def(py::init<double>(), "value"_a);

// 工厂：私有构造、需要返回智能指针、聚合类型
class Example {
private:
    Example(int);
public:
    static Example create(int a) { return Example(a); }
    static std::shared_ptr<Example> make(double d) { return std::make_shared<Example>(d); }
};

py::class_<Example>(m, "Example")
    .def(py::init(&Example::create))                                    // 值返回
    .def(py::init(&Example::make))                                      // holder 返回
    .def(py::init([](std::string s) { return new Example(1); }));       // 裸指针
```

`py::init<Args...>()` 内部用**花括号初始化**，因此也支持聚合类型；但要注意它会优先选择 `std::initializer_list` 重载，冲突时改用 `py::init(lambda)`。

### 8.3 方法、字段、属性

```cpp
py::class_<Account>(m, "Account")
    .def(py::init<double>(), "cash"_a)
    .def_property("cash", &Account::cash, &Account::set_cash)          // getter + setter
    .def_property_readonly("owner", &Account::owner)                   // 只读属性
    .def_readonly("id", &Account::id)                                  // 只读字段
    .def_readwrite("name", &Account::name)                             // 可写字段
    .def_static("create", &Account::create)                            // 静态方法
    .def_property_readonly_static("count", [](py::object /*self*/) { return 0; })
    .def("deposit", &Account::deposit, "amount"_a)
    .def("__repr__", [](const Account &a) { return "<Account>"; });
```

- `def_property` 的 getter 传 `nullptr` 即"只写属性"；
- 静态属性的 getter 仍会收到一个隐式参数（Python 的 `type` 对象），惯用写法是 `[](py::object /*self*/) {...}`；
- 一旦定义了 `__eq__` 却没定义 `__hash__`，`__hash__` 会变成 `None`（与 CPython 行为一致）。

### 8.4 继承、虚函数与 trampoline

让 Python 类能**继承 C++ 类并重写虚函数**，需要 trampoline（中转类）：

```cpp
class Strategy {
public:
    virtual ~Strategy() = default;
    virtual std::string name() const { return "Strategy"; }
    virtual double signal(const std::vector<double> &xs) const = 0;
};

class PyStrategy : public Strategy {
public:
    using Strategy::Strategy;                          // 继承构造函数

    std::string name() const override {
        PYBIND11_OVERRIDE_NAME(std::string, Strategy, "name", name);
    }
    double signal(const std::vector<double> &xs) const override {
        PYBIND11_OVERRIDE_PURE(double, Strategy, signal, xs);
    }
};

py::class_<Strategy, PyStrategy>(m, "Strategy")
    .def(py::init<>())
    .def("name", &Strategy::name)
    .def("signal", &Strategy::signal, "xs"_a);         // ← 绑真实类，不是 &PyStrategy::signal
```

| 宏 | 用途 |
| --- | --- |
| `PYBIND11_OVERRIDE(RT, Parent, name, args...)` | 父类有默认实现的虚函数 |
| `PYBIND11_OVERRIDE_PURE(RT, Parent, name, args...)` | 纯虚函数 |
| `PYBIND11_OVERRIDE_NAME(RT, Parent, "py_name", cpp_name, args...)` | C++ 与 Python 名字不同（如 `operator()` ↔ `__call__`） |

**踩坑清单**：

- **零参数虚函数要在实参位置留一个尾逗号**：`PYBIND11_OVERRIDE(std::string, Animal, name, );`
- 绑定时要绑 `&Animal::go`，**不要**绑 `&PyAnimal::go`；
- 继承链上**每一个**类（只要祖先有虚函数）都需要 trampoline，即使自己不新增虚函数；
- Python 侧子类必须显式调用绑定的 `__init__`，**不要用 `super()`**：

```python
class MyStrategy(example.Strategy):
    def __init__(self):
        example.Strategy.__init__(self)      # 漏掉会抛 TypeError
    def signal(self, xs):
        return sum(xs) / len(xs)
```

- v3 新增强制约定：**trampoline 配 `py::smart_holder` 时必须同时继承 `py::trampoline_self_life_support`**，否则编译失败：

```cpp
class PyAnimal : public Animal, public py::trampoline_self_life_support {
public:
    using Animal::Animal;
    std::string go(int n) override { PYBIND11_OVERRIDE_PURE(std::string, Animal, go, n); }
};
py::class_<Animal, PyAnimal, py::smart_holder>(m, "Animal").def(py::init<>()).def("go", &Animal::go);
```

我的实测结果：Python 子类重写 `signal()` 时走 Python 实现，不重写 `name()` 时自动回落到 C++ 的默认实现，两者都符合预期。

### 8.5 运算符重载

```cpp
#include <pybind11/operators.h>

py::class_<Price>(m, "Price")
    .def(py::init<double>(), "value"_a)
    .def(py::self + py::self)
    .def(py::self * double())
    .def(double() * py::self)          // 左操作数是内建类型时的自反形式
    .def(py::self == py::self)
    .def(py::self < py::self)
    .def(-py::self);
```

> 正确拼写是 `py::self`；**没有 `py::self_ns`**。`py::self <op> T` 等价于手写 `__op__` 并加 `py::is_operator()`（参数不匹配时返回 `NotImplemented`，给 Python 反射协议留机会）。

### 8.6 迭代器协议

```cpp
py::class_<Ticks>(m, "Ticks")
    .def(py::init<std::vector<double>>(), "values"_a)
    .def("__len__", [](const Ticks &t) { return t.values().size(); })
    .def("__iter__",
         [](const Ticks &t) { return py::make_iterator(t.values().begin(), t.values().end()); },
         py::keep_alive<0, 1>())                 // 迭代器存活期间保持 Ticks 存活
    .def("__getitem__", [](const Ticks &t, std::size_t i) {
        if (i >= t.values().size()) throw py::index_error("索引越界");
        return t.values()[i];
    });
```

`list(ticks)` 可用；`ticks[9]` 抛 `IndexError`（`py::index_error` → Python `IndexError`）。自定义迭代器里抛 `py::stop_iteration` 即转成 `StopIteration`。

### 8.7 枚举：v3 请用 `py::native_enum`

```cpp
#include <pybind11/native_enum.h>

enum class Side { Buy = 1, Sell = -1 };

py::native_enum<Side>(m, "Side", "enum.Enum")
    .value("Buy", Side::Buy, "买入")
    .value("Sell", Side::Sell, "卖出")
    .export_values()
    .finalize();                 // ← v3 必须调用
```

- 第二个参数是 Python 类型名，第三个是**完全限定**的 Python 基类名（`"enum.Enum"` / `"enum.IntEnum"`）；
- 与 `py::class_` 一样可挂在别的作用域下（如 `Pet.Kind`）；
- **`.finalize()` 必须调用**：Python 原生枚举不能增量构建，`native_enum` 先缓冲 name/value，`finalize()` 一次性构造；忘记调用会在析构时报 `MISSING .finalize()`；
- 实测：`isinstance(example.Side.Buy, enum.Enum)` 为 `True`，`.value == 1`。

旧写法 `py::enum_` 仍然可用但已废弃；它与 Python 习惯有一处不一致——**枚举值不要用 `is` 比较，要用 `==`**：

```cpp
py::enum_<Color>(m, "Color", py::arithmetic())   // 需要位运算/比较时加 py::arithmetic()
    .value("Red", Color::Red)
    .export_values();                            // 强类型 enum 建议不要 export_values（会污染父作用域）
```

### 8.8 序列化、动态属性与 buffer 协议

**(1) pickle（`copy`/`deepcopy` 也会用到）**

```cpp
py::class_<Point>(m, "Point")
    .def(py::init<int, int>(), "x"_a, "y"_a)
    .def_readwrite("x", &Point::x)
    .def_readwrite("y", &Point::y)
    .def(py::pickle(
        [](const Point &p) { return py::make_tuple(p.x, p.y); },        // __getstate__
        [](py::tuple t) {                                              // __setstate__（无 self）
            if (t.size() != 2) throw std::runtime_error("Invalid state!");
            return Point{t[0].cast<int>(), t[1].cast<int>()};
        }));
```

> 拼写是 `py::pickle`，**没有 `py::pickling`**。`pickle.dumps(obj, protocol)` 的 protocol 必须 ≥ 2。

**(2) `dynamic_attr()`：允许 Python 侧挂任意属性**

```cpp
py::class_<Point>(m, "Point", py::dynamic_attr()) ...;
// Python: p.tag = "extra" 可用，p.__dict__ == {'tag': 'extra'}
```

**(3) `def_buffer`：让自定义类型零拷贝变成 numpy 数组**

```cpp
py::class_<Matrix>(m, "Matrix", py::buffer_protocol())     // ← 必须带这个 tag
    .def_buffer([](Matrix &m) -> py::buffer_info {
        return py::buffer_info(
            m.data(), sizeof(float), py::format_descriptor<float>::format(),
            2, {m.rows(), m.cols()}, {sizeof(float) * m.cols(), sizeof(float)});
    });
```

**(4) 多模块同名类型冲突**

```text
ImportError: generic_type: type "Pet" is already registered!
```

给第三方库类型加 `py::module_local()` 即可：

```cpp
py::class_<pets::Pet>(m, "Pet", py::module_local()).def("name", &pets::Pet::name);
```

**(5) 私有析构 → 必须换 holder + `py::nodelete`**

```cpp
py::class_<Singleton, std::unique_ptr<Singleton, py::nodelete>>(m, "Singleton").def(py::init<>());
```

此时实例必须由 C++ 侧释放，否则泄漏。

---

## 第 9 章 类型转换体系

### 9.1 三层模型（先把概念理清）

| 层 | 例子 | 是否拷贝 |
| --- | --- | --- |
| C++ 原生 + Python 包装 | `py::class_` 注册的类 | **不拷贝**，按引用/指针传递 |
| C++ 包装 + Python 原生 | `py::list`、`py::dict`、`py::array` | **不拷贝**，只操作引用计数 |
| 双向原生转换（type_caster） | `int`、`std::string`、`std::vector` | **必然拷贝** |

这张表能解释很多疑惑：为什么 `std::vector` 传进 Python 后改它没用（拷贝），而 `py::list` 改它有用（同一个对象）。

### 9.2 自动转换一览

| C++ 类型 | Python 类型 | 需要的头文件 |
| --- | --- | --- |
| `int8_t`…`uint64_t`、`size_t`、`float`、`double`、`bool` | `int` / `float` / `bool` | `pybind11.h` |
| `char`、`std::string`、`string_view`（及各宽字符版本） | `str`（`bytes` 需显式 `py::bytes`） | `pybind11.h` |
| `std::pair`、`std::tuple` | `tuple` | `pybind11.h` |
| `std::vector/deque/list/array/set/map/unordered_*`、`optional`、`variant` | `list` / `set` / `dict` / `Optional[T]` | `stl.h` |
| `std::filesystem::path` | `pathlib.Path` | `stl/filesystem.h` |
| `std::function<R(A...)>` | callable | `functional.h` |
| `std::chrono::duration` / `time_point` | `timedelta` / `datetime` | `chrono.h` |
| `std::complex<T>` | `complex` | `complex.h` |
| `Eigen::Matrix/Map/SparseMatrix` | `numpy.ndarray` / scipy sparse | `eigen.h` |

几个容易踩的细节：

- `std::string` → Python 假定**有效 UTF-8**；非文本数据必须返回 `py::bytes(s)`；
- `str` → `std::string` 用 UTF-8，`bytes`/`bytearray` → `std::string` 则原样传入不做编码；
- `string_view` 的保活**只覆盖绑定函数调用期间**，存起来就会悬垂；
- v3 起 `float → int` **永远被拒绝**（防止 `1.9 → 1` 静默截断），超范围整数**加载失败**而非截断；
- `std::optional` 是表达"可空"的正道——`double*` 这类内建指针参数**不会**把 `None` 变成 `nullptr`。

### 9.3 容器：拷贝语义 vs opaque 绑定

```cpp
void append_1(std::vector<int> &v) { v.push_back(1); }
```

```python
>>> v = [5, 6]
>>> append_1(v)
>>> print(v)
[5, 6]        # ← 没变！vector 是拷贝式转换
```

需要**引用语义/就地修改**或想避免大容器每次跨界深拷贝时，用 opaque 绑定：

```cpp
#include <pybind11/stl_bind.h>

PYBIND11_MAKE_OPAQUE(std::vector<int>)       // 必须放在全局作用域、所有绑定代码之前
PYBIND11_MAKE_OPAQUE(std::map<std::string, double>)

py::bind_vector<std::vector<int>>(m, "IntVector");
py::bind_map<std::map<std::string, double>>(m, "MapStringDouble");
```

`bind_vector` 会一次性生成接近 `list` 的接口（`append`、`extend`、`insert`、`pop`、`clear`、`__getitem__` 含切片、`__len__`、`__iter__`、比较运算等）；`bind_map` 生成接近 `dict` 的接口（`keys/values/items` 视图、`__getitem__` 缺失抛 `KeyError` 等）。

`PYBIND11_MAKE_OPAQUE` 的硬性要求：**每个编译单元**都要在全局作用域声明一次，否则 ODR 问题。

### 9.4 自定义 `type_caster`

当 C++ 类型不适合用 `py::class_` 暴露，但你希望它在 Python 侧表现为一个自然的值（比如 `tuple`）时：

```cpp
namespace pybind11 { namespace detail {

template <>
struct type_caster<user_space::Point2D> {
    // 同时声明入参与返回值的类型注解
    PYBIND11_TYPE_CASTER(user_space::Point2D,
                         io_name("Sequence[float]", "tuple[float, float]"));

    // C++ -> Python
    static handle cast(const user_space::Point2D &p, return_value_policy /*policy*/,
                       handle /*parent*/) {
        return py::make_tuple(p.x, p.y).release();
    }

    // Python -> C++
    bool load(handle src, bool /*convert*/) {
        if (!py::isinstance<py::sequence>(src)) return false;
        auto seq = py::reinterpret_borrow<py::sequence>(src);
        if (seq.size() != 2) return false;
        value.x = seq[0].cast<double>();
        value.y = seq[1].cast<double>();
        return true;
    }
};

}} // namespace pybind11::detail
```

要点：`load` 失败要 `return false`（**不要抛异常**，那会破坏重载解析）；`PYBIND11_TYPE_CASTER` 会注入 `value`、`name` 以及各方向的操作符转换；`T` 必须可默认构造。

### 9.5 NumPy 互操作

**基础签名：**

```cpp
#include <pybind11/numpy.h>

// 输入：接受"任何能转成 C 连续 float64 数组"的对象（list 也行），内部零拷贝引用
py::array_t<double> moving_average(
    py::array_t<double, py::array::c_style | py::array::forcecast> xs, int window);
```

**关键事实：`array_t<T>` 的第二个模板参数默认就是 `forcecast`**，这意味着 **dtype 不匹配时会静默复制一份**：

```python
a = np.arange(5, dtype=np.int64)
example.fill_inplace(a, 7.0)     # 如果没有 noconvert，这里会拷贝 → a 不变
```

想要"零拷贝或直接报错"，三件套：

```cpp
// 1) 参数用 .noconvert()
m.def("fill_inplace",
      &fill_inplace,
      "xs"_a.noconvert(),          // ← 只接受完全匹配的数组
      "value"_a);
// 2) C++ 里 request() 拿裸指针
// 3) 确认可写：buf.readonly == false
```

**`py::buffer_info` 是统一的元信息入口：**

```cpp
py::dict buffer_info(py::buffer buf) {
    py::buffer_info bi = buf.request();
    py::dict d;
    d["ndim"] = bi.ndim;
    d["size"] = bi.size;
    d["itemsize"] = bi.itemsize;
    d["format"] = bi.format;        // 如 'd'、'l'
    d["shape"] = bi.shape;
    d["strides"] = bi.strides;
    return d;
}
```

注意 `buffer_info` 的**拷贝构造被删除**（只能移动），且其中的 `ptr` 只在对应 buffer 存活期间有效。

**零拷贝返回：必须给 `base`**

```cpp
// 有 base → ndarray 的 .base 指向它，从而保活 C++ 数据（零拷贝）
py::array_t<double> view(Matrix &m) {
    return py::array_t<double>({m.rows(), m.cols()}, {m.stride(), sizeof(double)},
                               m.data(), py::cast(&m));   // base = 拥有 m 的 Python 对象
}
// 没有 base → PyArray_NewCopy_ 复制一份
```

**性能写法：`unchecked` / `mutable_unchecked`**

```cpp
m.def("increment_3d", [](py::array_t<double> x) {
    auto r = x.mutable_unchecked<3>();      // ndim != 3 或不可写会抛 std::domain_error
    for (py::ssize_t i = 0; i < r.shape(0); ++i)
        for (py::ssize_t j = 0; j < r.shape(1); ++j)
            for (py::ssize_t k = 0; k < r.shape(2); ++k)
                r(i, j, k) += 1.0;
    return x;
}, py::arg().noconvert());
```

代理对象只在**构造时**快照 shape/strides/writeable，**数组被销毁或 reshape 后继续使用即为 UB**，请把作用域放到最小。

实测（零拷贝确实生效）：

```python
buf = np.zeros(4, dtype=np.float64)
example.fill_inplace(buf, 7.0)
assert (buf == 7.0).all()          # ✅ 真正原地修改，证明零拷贝
info = example.buffer_info(np.zeros((2, 3)))
assert info["ndim"] == 2 and info["shape"] == [2, 3]
```

### 9.6 用 `typing.h` 让签名"自解释"

```cpp
#include <pybind11/typing.h>

m.def("scale", [](py::typing::List<double> xs, double k) -> py::typing::List<double> { ... });
m.def("on_tick", [](py::typing::Callable<double(double) /* ⟵ 或 py::typing::Callable */> cb) { ... });
```

可用类型：`List<T>`、`Dict<K,V>`、`Set<T>`、`Tuple<...>`、`Iterable<T>`、`Iterator<T>`、`Callable<R(A...)>`、`Optional<T>`、`Union<Ts...>`、`Type<T>`、`Literal<...>`、`TypeVar<...>` 等。它们都是对应 `py::` 包装类的子类，**运行时零检查**，只为 IDE/静态检查/文档服务。

### 9.7 Eigen（点到为止）

```cpp
#include <pybind11/eigen.h>

// 传值：拷贝；传 const Ref：能映射就零拷贝（要求 dtype 与 stride 兼容）
m.def("scale_by_2", [](Eigen::Ref<Eigen::VectorXd> v) { v *= 2; });
m.def("big", &big, "a"_a.noconvert());        // 禁止"悄悄拷贝"

// 动态 stride：可映射 numpy 切片等任意布局
m.def("scale", [](py::EigenDRef<Eigen::MatrixXd> m, double c) { m *= c; });
```

三个高频坑：Eigen 默认 **ColMajor** 而 NumPy 默认 C 序（可用 `Eigen::RowMajor` 或 dynamic stride 解决）；非 const `Ref<>` 绝不接受临时拷贝，所以调用方必须传可写的连续数组；**不要返回 Eigen 表达式模板**（`a + b`、`m.transpose()`），那引用了已销毁的临时量。

---

## 第 10 章 异常、GIL 与生命周期

### 10.1 异常自动翻译

| C++ 抛出 | Python 收到 |
| --- | --- |
| `std::exception` | `RuntimeError` |
| `std::invalid_argument` / `std::domain_error` / `std::length_error` / `std::range_error` | `ValueError` |
| `std::out_of_range` | `IndexError` |
| `std::bad_alloc` | `MemoryError` |
| `std::overflow_error` | `OverflowError` |
| `py::index_error` / `py::key_error` / `py::value_error` / `py::type_error` | `IndexError` / `KeyError` / `ValueError` / `TypeError` |
| 其他任何异常 | `RuntimeError` |

> `py::index_error` 这类是**纯 C++ 类**，不是 Python 异常对象；翻译是单向的——想捕获来自 Python 的异常必须 `catch (py::error_already_set &)`。

**自定义异常：**

```cpp
struct RiskError : std::runtime_error { using std::runtime_error::runtime_error; };

py::register_exception<RiskError>(m, "RiskError", PyExc_RuntimeError);
// Python:
# try: example.check_leverage(5.0)
# except example.RiskError as e: ...     ✅
# except RuntimeError as e: ...               ✅ 也能捕获（基类）
```

**翻译任意第三方异常（无状态 lambda）：**

```cpp
struct VendorError { std::string message; };

py::register_exception_translator([](std::exception_ptr p) {
    try {
        if (p) std::rethrow_exception(p);
    } catch (const VendorError &e) {
        PyErr_SetString(PyExc_RuntimeError, e.message.c_str());   // 或 py::set_error(...)
    }
});
m.def("vendor_fail", []() { throw VendorError{"第三方库内部错误"}; });
```

规则：

- 翻译器按**注册逆序**执行，且所有 **local** 翻译器都先于 **global** 翻译器；
- 翻译器里**必须设置** Python 错误，否则会得到 `SystemError: error return without exception set`；
- 不打算处理的异常**不要 catch**，或显式重抛；
- 多个模块共享异常类型时用 `register_local_exception{,_translator}`，避免"谁后导入谁生效"的顺序依赖。

**跨语言传播：**

```cpp
// C++ 调用 Python：Python 异常变成 error_already_set
try {
    example.call_python(boom);           // Python 侧抛 KeyError
} catch (py::error_already_set &e) {
    if (e.matches(PyExc_KeyError)) { /* ... */ }
    throw;
}
```

`error_already_set::what()` 会获取 GIL；`discard_as_unraisable()` 用于 `noexcept` 上下文（尤其**析构函数**）：

```cpp
~MyClass() {
    try {
        py::exec("raise ValueError('boom')");
    } catch (py::error_already_set &e) {
        e.discard_as_unraisable(__func__);     // 否则异常逸出 noexcept 析构 → std::terminate()
    }
}
```

### 10.2 GIL：最容易被忽视的一条规则

> **pybind11 从不会隐式释放 GIL。** 它只会在"知道自己要调用 Python"时自动获取（比如回调、trampoline）。

因此：**计算密集的纯 C++ 代码必须自己释放 GIL**，否则多线程 Python 程序完全没有并发。

```cpp
// 方式一：作用域 RAII（推荐，粒度可控）
double busy_sum_releasing_gil(std::size_t n) {
    py::gil_scoped_release release;      // 从这行到作用域结束，不持有 GIL
    return busy_sum(n);                  // ← 这里绝对不能碰任何 Python 对象
}

// 方式二：call_guard 一行搞定
m.def("busy_sum_releasing_gil", &busy_sum_releasing_gil, py::call_guard<py::gil_scoped_release>());
```

反向操作：C++ 工作线程里要回 Python 时，必须**先获取 GIL**：

```cpp
void run_callback_in_thread(py::function cb) {
    std::thread worker([cb = std::move(cb)]() mutable {
        py::gil_scoped_acquire acquire;   // 进入 Python 前获取 GIL
        cb(42);
    });
    {
        py::gil_scoped_release release;   // ★ join 期间必须让出 GIL，否则死锁
        worker.join();
    }
}
```

#### 我在实测中真的踩到的死锁（强烈建议记住）

我最初把上面写成了这样：

```cpp
void run_callback_in_thread(py::function cb) {
    std::thread worker([cb]() { py::gil_scoped_acquire acquire; cb(42); });
    worker.join();        // ❌ 主线程仍持有 GIL，worker 永远拿不到 → 永久挂起
}
```

结果是自检脚本**卡死不动**，直到我被 120 s 超时打断才意识到问题。原因非常典型：

```text
主线程：持有 GIL ──► 等待 worker 结束（join）
worker：等待 GIL ──► 才能执行回调
→ 经典环路等待，死锁
```

修复方式就是上面代码里的 `py::gil_scoped_release`。**结论：任何"主线程 join 子线程，而子线程要回 Python"的代码，join 之前必须让出 GIL。**

#### 实测数据：释放 GIL 到底有多大差别

我做了一个实验来验证：主线程调用 C++ 计算，同时另一个 Python 线程不停地自增计数器。

```python
th = threading.Thread(target=spin); th.start()
t0 = time.perf_counter()
example.busy_sum_holding_gil(60_000_000)     # 或 busy_sum_releasing_gil
elapsed = time.perf_counter() - t0
```

实测输出：

```text
持有 GIL: C++ 耗时 62 ms，期间 Python 线程自增 87,097 次
释放 GIL: C++ 耗时 63 ms，期间 Python 线程自增 1,033,183 次
```

同样 62 ms 左右的窗口内，释放 GIL 后 Python 线程的工作量提升了 **约 12 倍**（87k → 1.03M 次）。这就是"为什么你的 C++ 扩展没有让多线程变快"的答案。

#### free-threaded（no-GIL）与子解释器

```cpp
PYBIND11_MODULE(example, m, py::mod_gil_not_used()) {
    // 声明：本模块线程安全，可在 free-threaded Python 3.13+ 上运行
}
```

- 这个 tag 是**你对"线程安全"的承诺**，不是自动变安全的开关；模块还必须针对 free-threading 分支编译；
- free-threaded 下改写 Python 对象要用 `py::scoped_critical_section`（`#include <pybind11/critical_section.h>`），且**不可嵌套**、不要与 `std::mutex` 混用；
- 子解释器（Python 3.12+ 各自独立 GIL）用 `py::subinterpreter` + `py::subinterpreter_scoped_activate`；**绝不跨解释器共享 Python 对象**，也**不要让 `error_already_set` 越过 `subinterpreter_scoped_activate` 边界**。

### 10.3 生命周期与所有权

**holder 的选择：**

| holder | 特点 |
| --- | --- |
| `std::unique_ptr<T>`（默认） | 轻量，但**只支持 C++ → Python**；把 `unique_ptr` 作为参数会在运行期失败 |
| `std::shared_ptr<T>` | 与 Python 引用计数协同；但一个类型只能有一个 holder，混用 `unique_ptr` 会段错误 |
| `py::smart_holder`（v3 推荐） | `unique_ptr`/`shared_ptr` **双向**安全转换、支持 `enable_shared_from_this`、避免继承切片；`py::classh<T>` 是简写 |

```cpp
py::class_<Account, std::shared_ptr<Account>>(m, "Account")
    .def_static("create", &Account::create);      // 工厂返回 shared_ptr
```

**什么时候必须显式写返回策略：**

```cpp
// 返回指向静态/全局对象的裸指针 —— 不写策略就会 double free
m.def("get_config", &get_config, py::return_value_policy::reference);

// 返回成员引用 —— reference_internal 让父对象保活
.def("weights_ref", &weights_of, py::return_value_policy::reference_internal)
```

**官方反复强调的一条原则**：优先用**智能指针**表达所有权，而不是靠人肉记忆策略。智能指针能告诉 pybind11 "这个对象 C++ 侧还有没有引用"。

**验证生命周期是否正确的办法**（我用的手法）：给对象加存活计数。

```cpp
struct Tracked {
    static int alive;
    explicit Tracked(std::string t) : tag(std::move(t)) { ++alive; }
    Tracked(const Tracked &o) : tag(o.tag) { ++alive; }
    ~Tracked() { --alive; }
};
```

```python
assert example.tracked_alive() == 0
t1 = example.make_tracked_by_value("copy")          # 按值返回：拷贝进 Python
assert example.tracked_alive() == 1
t2 = example.make_tracked_by_ownership("owned")     # 移交所有权
assert example.tracked_alive() == 2
del t1, t2
assert example.tracked_alive() == 0                 # ✅ Python GC 正确释放
```

**循环引用提醒**：`keep_alive` 建立的是强引用，本身可能制造循环，需要 Python 的 GC（而非纯引用计数）才能回收。

---

## 第 11 章 嵌入 Python：把解释器装进 C++ 程序

### 11.1 最小可运行程序

```cpp
#include <pybind11/embed.h>
namespace py = pybind11;

int main() {
    py::scoped_interpreter guard{};        // 启动解释器，离开作用域自动 finalize
    py::print("Hello, World!");
}
```

```cmake
add_executable(example_embed embed/embed_main.cpp)
target_link_libraries(example_embed PRIVATE pybind11::embed)   # ← 注意是 embed，不是 module
```

### 11.2 执行代码、取值、调用库

```cpp
int main() {
    py::scoped_interpreter guard{};

    // 1) 执行任意 Python 代码
    py::exec(R"(
import math
print("sqrt(16) =", math.sqrt(16))
)");

    // 2) 求值并取回 C++ 值
    int total = py::eval("sum(i * i for i in range(10))").cast<int>();   // 285

    // 3) 调用第三方库
    py::object np = py::module_::import("numpy");
    py::object arr = np.attr("array")(py::make_tuple(1.0, 2.0, 3.0, 4.0));
    double mean = arr.attr("mean")().cast<double>();                     // 2.5

    // 4) Python 异常翻译成 C++ 异常
    try {
        py::exec("raise ValueError('boom from python')");
    } catch (const py::error_already_set &e) {
        std::cout << "caught: " << e.what() << '\n';
    }

    // 5) 把 C++ 值注入 Python 命名空间
    py::exec("print('injected:', cpp_value * 2)",
             py::globals(), py::dict("cpp_value"_a = 21));
    return 0;
}
```

**我在本机的真实输出**：

```text
[embed] Python 3.12.0 (tags/v3.12.0:0fb18b0, Oct  2 2023, 13:03:39) [MSC v.1935 64 bit (AMD64)]
[embed] from exec: 4.0
[embed] eval result = 285
[embed] numpy mean = 2.5
[embed] injected: 42
[embed] caught: ValueError: boom from python
```

### 11.3 必须遵守的生命周期纪律

```cpp
{ // ❌ BAD：hello 的析构发生在解释器关闭之后
    py::initialize_interpreter();
    auto hello = py::str("Hello");
    py::finalize_interpreter();
}   // ← 崩溃

{ // ✅ GOOD
    py::scoped_interpreter guard{};
    auto hello = py::str("Hello");
}   // hello 先析构，解释器后关闭
```

其他规则：

- **两个并发的 `scoped_interpreter` 是致命错误**；解释器已初始化后再调 `initialize_interpreter` 同样；
- **不要**直接用裸 `Py_Initialize` / `Py_Finalize`，用 pybind11 的 RAII 包装；
- 嵌出/嵌入时，**当前工作目录会自动加入 `sys.path`**，所以同目录的 `.py` 可以直接 `import`；
- 想给 Python 侧提供"内建模块"，用 `PYBIND11_EMBEDDED_MODULE(name, m) { ... }`（全局作用域，写法与 `PYBIND11_MODULE` 一致）。

### 11.4 什么时候值得嵌入

- 现有 C++ 宿主程序（行情网关、回测引擎、工业软件）需要脚本化策略；
- 想让用户用 Python 写策略、而把执行留在 C++ 的线程与内存模型里；
- 需要复用 Python 生态（pandas/numpy/可视化）做结果分析。

反过来要清醒：嵌入会把 Python 解释器与 GIL 引进你的进程，增加初始化开销与部署复杂度；如果只是"调用一次 Python 脚本"，直接用子进程可能更省事。

---

## 第 12 章 学习经验与注意事项

学 pybind11 的过程中，真正让我卡住的往往不是 API 本身，而是"报错看不懂""跑起来莫名其妙崩了""以为优化了实际更慢"。这一章专门记录这些经验。

### 12.1 写完就测：用测试验证自己的理解

pybind11 的很多行为**不能靠猜**，尤其是类型转换与生命周期。我的做法是每写一组绑定，就配一个 Python 侧的自检脚本，把"我以为的行为"写成断言：

```python
def check(label, cond):
    assert cond, f"FAILED: {label}"
    print(f"  ok  {label}")

check("add", example.add(1, 2) == 3)
check("容器转换是拷贝", example.take_vector([1, 2, 3]) == 3)
check("越界抛 IndexError", raises(IndexError, lambda: example.item(99)))
```

经验：**值得专门验证的四类行为**

| 类别 | 举例 | 为什么必须测 |
| --- | --- | --- |
| 参数边界 | 空容器、越界索引、传 `None` | 这些是 C++ 侧最容易漏判的分支 |
| 异常类型 | `std::invalid_argument` 是否真的变成 `ValueError` | 翻译规则要自己确认一遍 |
| 生命周期 | 对象在 Python 侧释放后，C++ 计数是否归零 | 所有权策略写错时**不会报错**，只会崩或泄漏 |
| GIL | 计算期间另一个 Python 线程能否推进 | 忘了释放 GIL 时程序完全正常，只是没有并发 |

上面几类里，**生命周期、GIL、以及"改了没生效"的容器拷贝语义**都属于**静默失败**——程序不报错，只是行为和你以为的不一样。这正是它们值得花时间写测试的原因。

### 12.2 调试：把"模板天书"变成人话

**(1) 打开详细错误信息**

```cmake
# 编译期定义，能显著改善类型转换失败时的报错
target_compile_definitions(mymod PRIVATE PYBIND11_DETAILED_ERROR_MESSAGES)
```

默认情况下 `py::cast` 失败只会说 `to C++ type '?'`；打开后（或用 Debug 构建）会带上真实类型名。

**(2) 编译期模板报错怎么读**

pybind11 的报错又长又吓人，但**结论通常在最后几行**。固定套路：

```text
1. 直接跳到输出末尾，找 "error:" 所在的那几行（前面的都是模板实例化栈）
2. 找"谁无法转换"：常见是 missing type_caster —— 多半忘了 include 对应头文件
   （std::vector → 忘了 stl.h；std::function → 忘了 functional.h；
     py::array_t → 忘了 numpy.h；自定义枚举 → 版本/注册冲突）
3. 找 "invalid use of incomplete type" —— 类没注册或定义顺序不对
4. 找 recursive template instantiation exceeded maximum depth —— 加 -ftemplate-depth=1024
```

**(3) 运行期崩溃怎么定位**

| 症状 | 最可能的原因 |
| --- | --- |
| `ImportError: dynamic module does not define ... PyInit_X` | 模块名与文件名不一致 |
| `ImportError: DLL load failed`（Windows） | 缺 DLL（MinGW 忘加 `-static`）或架构/版本不符 |
| 段错误（segfault）且无 traceback | 生命周期问题：悬垂引用、双重所有权、GIL 期间碰 Python |
| `SystemError: error return without exception set` | 自定义异常翻译器忘了设置 Python 错误 |
| 死锁/挂起 | GIL 环路等待（第 10.2 节的真实案例） |
| 内存持续增长 | 循环引用、`py::nodelete` 忘记手动释放、`return_value_policy` 用错 |

实用手段：

```powershell
# 看扩展模块真实依赖了哪些 DLL
& 'D:\study\MinGW\mingw64\bin\objdump.exe' -p build\example.cp312-win_amd64.pyd | Select-String 'DLL Name'
# MSVC 用
dumpbin /dependents build\example.cp312-win_amd64.pyd
```

```python
# Python 侧：崩溃前打印 Python 栈，能定位到调用点
import faulthandler; faulthandler.enable()
# 或在命令行
# python -X faulthandler your_test.py
```

GIL 相关的死锁可以用调试器确认：`p PyGILState_Check()` 看当前线程是否持有 GIL，`thread apply all p PyGILState_Check()` 找出持有者。

### 12.3 性能：先量，再优化

**(1) 编译期优化**（详见 6.7）

| 手段 | 效果 |
| --- | --- |
| `PRECOMPILE`（v3.2） | pybind11 非模板部分按 build tree 只编译一次 |
| 拆分翻译单元 | 单 TU 内存下降、可并行、增量快 |
| `target_precompile_headers` | 减少重复解析头文件 |
| 编译缓存（ccache/sccache） | 重复构建加速 |

**(2) 运行期优化**

| 手段 | 说明 |
| --- | --- |
| 传数组而不是传容器 | `py::array_t`/`Eigen::Ref` 零拷贝；`std::vector` 参数要整段转换 |
| 批量调用 | 一次跨界处理 N 条数据，而不是 N 次跨界 |
| 释放 GIL | 长计算不再阻塞其他 Python 线程（实测差 12 倍） |
| 用 `unchecked<>()` | 省掉每次索引的边界检查 |
| 减少拷贝 | 用 `.noconvert()` 让"悄悄拷贝"变成显式错误 |
| 避免在热路径创建 Python 对象 | `py::str`/`py::list` 的构造与引用计数都要钱 |

**(3) 一个容易被忽略的陷阱：跨界调用的固定开销**

一次跨语言调用大约在**百纳秒级**。如果你把一次 C++ 调用拆成"循环里每元素调一次 Python"，你会比纯 Python 还慢。**正确的粒度是"一次调用处理一整批数据"**。

### 12.4 几条经验小结

学完这一圈，我自己总结下来最值钱的几条：

1. **功能不生效，先查头文件**。`std::vector` 要 `stl.h`、回调要 `functional.h`、数组要 `numpy.h`、原生枚举要 `native_enum.h`——新手第一大坑，占了我一半的"为什么编译不过"。
2. **报错看末尾**。pybind11 的模板报错有几十上百行，真正有用的就最后那几行 `error:`。
3. **所有权的坑都是静默的**。返回值策略、holder、`keep_alive` 写错时编译通过、运行也可能"看起来正常"，然后随机崩溃。优先用智能指针，拿不准就写生命周期计数测试。
4. **GIL 要手动释放**。pybind11 从不隐式释放 GIL；计算密集的 C++ 段不写 `gil_scoped_release`，你的多线程 Python 程序不会有任何加速。
5. **构建系统的知识比语法更费时间**。ABI 后缀、`pybind11_add_module`、跨平台差异——这些"非算法"的东西，是最容易卡住初学者的地方。
6. **能用 NumPy 就不用 C++**。向量化能表达的运算，NumPy 往往更快；C++ 的优势在有状态、有分支、无法向量化的循环里。
7. **先量再优化**。我一开始以为"只要换成 C++ 就快"，实际上一部分时间花在了跨语言的数据转换上；不测一下，根本不知道瓶颈在哪。

---

## 第 13 章 踩坑记录与 FAQ

### 13.1 复盘 `log.txt` 里的两个真实报错

**(1) `cmake ..` 在错误的目录执行**

```text
PS D:\...\Quantify\pybind11> mkdir build
PS D:\...\Quantify\pybind11> cmake ..
CMake Warning: Ignoring extra path from command line: ".."
CMake Error: The source directory "D:/study/programming/python/project/Quantify"
does not appear to contain CMakeLists.txt.
```

原因：此时 CWD 是 `...\Quantify\pybind11`，`..` 指向父目录 `...\Quantify`（那里没有 CMake 配置）。修正就是日志里后来做的 `cd build` 再 `cmake ..`。**更稳的写法是永远用 `-S`/`-B`**：

```powershell
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DPYBIND11_FINDPYTHON=ON
```

**(2) `-- pybind11::lto disabled (problems with undefined symbols for MinGW for now)`**

这**不是错误**，是预期行为：`tools/pybind11Common.cmake` 对 MinGW 直接跳过 LTO 生成。不必排查；若你的工具链确已支持，可自己接管：`set(CMAKE_INTERPROCEDURAL_OPTIMIZATION ON)`。

**(3) 顺带一提：`Using compatibility mode for Python ...`**

```text
Using compatibility mode for Python, set PYBIND11_FINDPYTHON to NEW/OLD to silence this message
```

`add_subdirectory` 模式下 `PYBIND11_FINDPYTHON` 默认是 `COMPAT`。加 `set(PYBIND11_FINDPYTHON ON)`（或 `-DPYBIND11_FINDPYTHON=ON`）即可消除。

### 13.2 对本仓库现有示例工程的五条改进建议

| 文件 | 建议 | 原因 |
| --- | --- | --- |
| `CMakelists.txt` | 改名为 `CMakeLists.txt` | Linux/macOS 上大小写敏感，会找不到 |
| `CMakelists.txt` 第 4–5 行 | 删除 `set(PYTHON_EXECUTABLE "")` / `set(PYTHON_INCLUDE_DIRECTORY "")` | v3.0 起 `PYTHON_*` 已失效；后者根本不是合法变量名 |
| `CMakelists.txt` | 增加 `set(PYBIND11_FINDPYTHON ON)` | 消除兼容模式警告 |
| `build/` | 加进 `.gitignore` | 里面是 `CMakeCache.txt`、`.obj`、`.ninja_deps` 等生成物 |
| `test.cpp` | 删除 | 与 pybind11 工程无关的 Hello World，容易误导读者 |

改完后的构建命令：

```powershell
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DPYBIND11_FINDPYTHON=ON
cmake --build build
```

### 13.3 API 拼写"假朋友"清单（写在代码里就会编译不过）

| 你可能写的 | 实际正确的 | 说明 |
| --- | --- | --- |
| `return_value_policy::none` | ❌ 不存在 | 返回 `None` 用 `py::none()` / `void` / `std::optional` |
| `py::self_ns` | `py::self` | operators.h 里只有 `py::self` |
| `py::pickling` | `py::pickle` | 序列化用 `py::pickle(getstate, setstate)` |
| 独立的 `py::noconvert()` | `py::arg("x").noconvert()` | 没有独立标签 |
| `gil_scoped_release(nosave)` | `py::gil_scoped_release(bool disassoc = false)` | `no_save` 是 PyTorch 的 API |
| `py::class_<T>` 里传 type_caster | holder 用 `PYBIND11_DECLARE_HOLDER_TYPE` | type_caster 不是 class_ 模板参数 |
| `py::module` | 可以用（是 `module_` 的别名） | 新代码推荐 `py::module_` |

### 13.4 高频运行期错误速查

| 错误信息 | 原因 | 解决 |
| --- | --- | --- |
| `dynamic module does not define module export function (PyInit_X)` | 模块名 ≠ 文件名 | 让 `PYBIND11_MODULE(X, m)` 的 X 与目标名一致 |
| `generic_type: type "X" is already registered!` | 两个模块注册了同一 C++ 类型 | 加 `py::module_local()` |
| `TypeError: incompatible function arguments` | 参数类型不匹配（重载全失败） | 打开 `PYBIND11_DETAILED_ERROR_MESSAGES` 看真实类型 |
| `RuntimeError: Could not activate keep_alive!` | `keep_alive` 索引写错 | 0=返回值、1=self、实参从 2 开始 |
| `SystemError: error return without exception set` | 翻译器没设置 Python 错误 | 用 `PyErr_SetString` / `py::set_error` |
| 访问数组时 `std::domain_error` | 数组只读或 `ndim` 不符 | 检查 `writeable()` 与维度，或用 `request()` |
| 段错误，且只在使用某对象后出现 | 悬垂引用 / 双重所有权 | 用智能指针，或显式 `return_value_policy` + `keep_alive` |
| 程序挂起（无 CPU 占用） | GIL 环路等待 | 见 10.2 节：join 前释放 GIL |
| `ImportError: DLL load failed`（MinGW） | 缺 `libwinpthread-1.dll` | 加 `-static` 重新编译 |
| `'PyGILState_Check' was not declared in this scope` | 定义了 `Py_LIMITED_API` | pybind11 不支持 Stable ABI，去掉该定义 |
| `recursive template instantiation exceeded maximum depth of 256` | 模板实例化太深 | `-ftemplate-depth=1024` |

### 13.5 设计层面的十个"别做"

1. 别对指向静态对象的裸指针用默认返回策略（会 double free）。
2. 别在 `py::gil_scoped_release` 作用域里碰任何 Python 对象。
3. 别让 Python 对象活得比解释器长。
4. 别在析构函数里让 Python 异常逃逸（用 `discard_as_unraisable`）。
5. 别在模块初始化时写"只执行一次"的全局副作用（会为每个解释器各跑一次）。
6. 别在 block-scope `static` 变量的初始化里调用 Python（锁序死锁）。
7. 别把 `std::vector` 参数当成"引用语义"用（它是深拷贝）。
8. 别让 `array_t` 的 `forcecast` 帮你"悄悄修好" dtype（就地修改会失效）。
9. 别返回 Eigen 表达式模板或没有 base 的 `py::array`。
10. 别在热路径上做"每个元素一次跨界调用"的设计。

---

## 附录 常用 API 速查表

**模块与函数**

```cpp
PYBIND11_MODULE(name, m [, tags...])   // 模块定义
PYBIND11_EMBEDDED_MODULE(name, m)      // 嵌入式模块
m.doc() = "...";                       // 模块 docstring
m.attr("__version__") = "1.0.0";       // 模块属性
m.def_submodule("sub", "doc");         // 子模块
m.def("f", &f, "doc", "a"_a, "b"_a = 1, py::arg("c").noconvert(),
      py::kw_only(), py::return_value_policy::copy,
      py::keep_alive<1, 2>(), py::call_guard<py::gil_scoped_release>());
```

**类**

```cpp
py::class_<T> / py::class_<T, Base> / py::classh<T>            // 绑定类 / 基类 / smart_holder 简写
  .def(py::init<Args...>())                                     // 构造
  .def(py::init(&Factory::create))                              // 工厂
  .def("m", &T::m, "doc", "arg"_a)
  .def_static("s", &T::s)
  .def_property("p", &T::get, &T::set)                          // 属性
  .def_property_readonly("r", &T::get)
  .def_readwrite("f", &T::f) / .def_readonly(...)
  .def("__repr__", [](const T &t) { return "..."; })
  .def(py::pickle(getstate, setstate))
  .def_buffer([](T &t) -> py::buffer_info { ... });
```

**类型转换与 GIL**

```cpp
py::cast<T>(obj);  obj.cast<T>();                               // 显式转换
py::gil_scoped_acquire / py::gil_scoped_release                 // GIL RAII
py::call_guard<py::gil_scoped_release>()                        // 函数级释放
py::mod_gil_not_used() / py::mod_gil_used()                     // 模块能力声明
py::array_t<T, py::array::c_style | py::array::forcecast>       // numpy 数组
buf.request();                                                  // buffer_info
py::typing::List<T> / Dict<K,V> / Callable<R(A...)>             // 类型注解
```

**异常**

```cpp
py::register_exception<E>(m, "E" [, base]);
py::register_exception_translator([](std::exception_ptr p) { ... });
throw py::value_error("...");  throw py::index_error("...");
catch (py::error_already_set &e) { e.matches(PyExc_KeyError); e.discard_as_unraisable(__func__); }
```

**头文件对照**

| 需要什么 | include |
| --- | --- |
| 一切的基础 | `..` |
| `vector/map/set/optional/variant` | `..` |
| 就地修改容器 | `..` + `PYBIND11_MAKE_OPAQUE` |
| 回调 | `..` |
| 数组 | `..` |
| Eigen | `..` |
| 时间/复数 | `..`、`..` |
| 运算符糖 | `..` |
| 嵌入 | `..` |
| 原生枚举（v3） | `..` |
| 类型注解 | `..` |

---

## 结语

把 pybind11 学下来，我自己的最大体会是：**它难的不是 API，而是那些不会报错的东西。**

1. **一个宏 + 一个转换器**：`PYBIND11_MODULE` 负责生成模块入口，`type_caster` 负责 Python ↔ C++ 的双向搬运，`py::class_` 负责给自定义类型注册"身份"。理解这三者，剩下的 API 基本都是它们的组合。
2. **所有权与生命周期是最深的坑**：返回值策略、holder、`keep_alive`、`reference_internal`、GIL——出问题几乎都集中在这里，而且往往是静默的。**优先用智能指针表达所有权，拿不准就写测试验证。**
3. **构建系统是绕不过去的门槛**：ABI 后缀、`pybind11_add_module`、跨平台差异。这些"非算法"的知识最容易劝退初学者，但也最值得先搞明白。

这份笔记就记到这里。以后再遇到新的坑，我打算继续往第 13 章里补。