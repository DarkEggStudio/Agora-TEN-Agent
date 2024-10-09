/**
 *
 * Agora Real Time Engagement
 * Created by Wei Hu in 2022-02.
 * Copyright (c) 2024 Agora IO. All rights reserved.
 *
 */
#include <cstring>

#include "rte_runtime/binding/cpp/rte.h"
#include "rte_runtime/binding/python/common.h"
#include "utils/container/list_str.h"
#include "utils/lib/module.h"
#include "utils/lib/path.h"
#include "utils/lib/string.h"
#include "utils/log/log.h"
#include "utils/macro/check.h"

static void foo() {}

/**
 * This addon is used for those rte app whose "main" function is not written in
 * python. By putting this addon into a rte app, the python runtime can be
 * initialized and other python addons can be loaded and registered to the rte
 * world when the rte app is started.
 *
 * Time sequence:
 *
 * 0) The executable of the rte app (non-python) links with librte_runtime.
 *
 * 1) The program of the rte app (non-python) is started, with librte_runtime
 *    being loaded, which triggers this addon to be dlopen-ed.
 *
 * 2) librte_runtime will call 'rte_addon_register_extension()' synchronously,
 *    then py_init_addon_t::on_init() will be called from librte_runtime.
 *
 * 3) py_init_addon_t::on_init() will handle things including Py_Initialize,
 *    setup sys.path, load all python addons in the app's addon/ folder.
 *
 * 4) librte_runtime_python will be loaded when any python addon is loaded (due
 *    to the python code: 'import librte_runtime_python')
 *
 * 5) After all python addons are registered, py_init_addon_t::on_init() will
 *    release the python GIL so that other python codes can be executed in any
 *    other threads after they acquiring the GIL.
 *
 * ================================================
 * What will happen if the app is a python program?
 *
 * If no special handling is done, there will be the following 2 problems:
 *
 * 1) Python prohibits importing the same module again before it has been fully
 *    imported (i.e., circular imports). And if the main program is a python
 *    program, and if the main program loads librte_runtime_python (because it
 *    might need some features in it), python addons will be loaded after
 *    librte_runtime_python is imported (because librte_runtime_python will
 *    loads librte_runtime, and librte_runtime will loop addon/ folder to
 *    load/dlopen all the _native_ addons in it, and it will load
 *    py_init_extension, and this py_init_extension will load all python addons
 *    in addon/ folder). And if these loaded Python addons load
 *    librte_runtime_python (because they need to use its functionalities),
 *    which will create a circular import.
 *
 * 2. If the main program is a python program and it loaded this addon
 *    _synchronously_ in the python main thread (see above), then if the GIL is
 *    released in py_init_addon_t::on_init, then no more further python codes
 *    can be executed normally in the python main thread.
 *
 * 3. Even though the app is not a python program, if the python
 *    multiprocessing mode is set to 'spawn', then the subprocess will be
 *    executed by a __Python__ interpreter, not the origin native executable.
 *    While if the 'librte_runtime_python' module is imported before the target
 *    function is called in subprocess (For example, if the Python module
 *    containing the target function or its parent folder's Python module
 *    imports rte_runtime_python.) (And this situation is similar to the python
 *    main situation), then librte_runtime will be loaded again, which will
 *    cause this addon to be loaded. Which results in a circular import similar
 *    to the situation described above.
 *
 * How to avoid any side effects?
 *
 * The main reason is that, theoretically, python main and py_init_extension
 * should not be used together. However, due to some reasonable or unreasonable
 * reasons mentioned above, python main and py_init_extension are being used
 * together. Therefore, what we need to do in this situation is to detect this
 * case and then essentially disable py_init_extension. By checking
 * 'rte_py_is_initialized' on py_init_addon_t::on_init, we can know whether the
 * python runtime has been initialized. And the calling operation here is thread
 * safe, because if the app is not a python program, the python runtime is not
 * initialized for sure, and if the app is a python program, then the
 * py_init_addon_t::on_init will be called in the python main thread and the GIL
 * is held, so it is thread safe to call 'rte_py_is_initialized'.
 */

namespace default_extension {

class py_init_addon_t : public rte::addon_t {
 public:
  explicit py_init_addon_t() = default;

  // Get the real path of <app_root>/addon/extension/
  static rte_string_t *get_addon_extensions_path() {
    rte_string_t *module_path =
        rte_path_get_module_path(reinterpret_cast<const void *>(foo));
    RTE_ASSERT(module_path, "Failed to get module path.");

    rte_string_concat(module_path, "/../..");

    rte_string_t *real_path = rte_path_realpath(module_path);
    rte_string_destroy(module_path);

    if (real_path == nullptr) {
      RTE_LOGE("Failed to get real path of addon extensions.");
      return nullptr;
    }

    return real_path;
  }

  // Load all python addons by import modules.
  static void load_all_python_modules(rte_string_t *addon_extensions_path) {
    if (addon_extensions_path == nullptr ||
        rte_string_is_empty(addon_extensions_path)) {
      RTE_LOGE(
          "Failed to load python modules due to empty addon extension path.");
      return;
    }

    rte_dir_fd_t *dir = rte_path_open_dir(addon_extensions_path);
    if (dir == nullptr) {
      RTE_LOGE("Failed to open directory: %s when loading python modules.",
               rte_string_get_raw_str(addon_extensions_path));
      return;
    }

    rte_path_itor_t *itor = rte_path_get_first(dir);
    while (itor != nullptr) {
      rte_string_t *short_name = rte_path_itor_get_name(itor);
      if (short_name == nullptr) {
        RTE_LOGE(
            "Failed to get short name under path %s, when loading python "
            "modules.",
            addon_extensions_path->buf);
        itor = rte_path_get_next(itor);
        continue;
      }

      if (!(rte_string_is_equal_c_str(short_name, ".") ||
            rte_string_is_equal_c_str(short_name, ".."))) {
        // The full module name is "addon.extension.<short_name>"
        rte_string_t *full_module_name =
            rte_string_create_with_value("addon.extension.%s", short_name->buf);
        rte_py_import_module(full_module_name->buf);
        rte_string_destroy(full_module_name);
      }

      rte_string_destroy(short_name);
      itor = rte_path_get_next(itor);
    }

    if (dir != nullptr) {
      rte_path_close_dir(dir);
    }
  }

  static void load_python_lib() {
    rte_string_t *python_lib_path =
        rte_string_create_with_value("librte_runtime_python.so");

    // The librte_runtime_python.so must be loaded globally using dlopen, and
    // cannot be a regular shared library dependency. Note that the 2nd
    // parameter must be 0 (as_local = false).
    //
    // Refer to
    // https://mail.python.org/pipermail/new-bugs-announce/2008-November/003322.html
    rte_module_load(python_lib_path, 0);

    rte_string_destroy(python_lib_path);
  }

  // Setup python system path and make sure following paths are included:
  // <app_root>/lib
  // <app_root>/interface
  // <app_root>
  static void complete_sys_path() {
    rte_list_t paths;
    rte_list_init(&paths);

    rte_string_t *module_path =
        rte_path_get_module_path(reinterpret_cast<const void *>(foo));
    RTE_ASSERT(module_path, "Failed to get module path.");

    rte_string_concat(module_path, "/../../../..");
    rte_string_t *app_root = rte_path_realpath(module_path);
    rte_string_destroy(module_path);

    rte_string_t *lib_path = rte_string_create_with_value(
        "%s/lib", rte_string_get_raw_str(app_root));
    rte_string_t *interface_path = rte_string_create_with_value(
        "%s/interface", rte_string_get_raw_str(app_root));

    rte_list_push_str_back(&paths, rte_string_get_raw_str(lib_path));
    rte_list_push_str_back(&paths, rte_string_get_raw_str(interface_path));
    rte_list_push_str_back(&paths, rte_string_get_raw_str(app_root));

    rte_string_destroy(app_root);
    rte_string_destroy(lib_path);
    rte_string_destroy(interface_path);

    rte_py_add_paths_to_sys(&paths);

    rte_list_clear(&paths);
  }

  void on_init(rte::rte_env_t &rte_env,
               rte::metadata_info_t &property) override {
    // Do some initializations.

    RTE_LOGI("py_init_addon_t::on_init");

    int py_initialized = rte_py_is_initialized();
    if (py_initialized != 0) {
      RTE_LOGI("Python runtime has been initialized.");
      rte_env.on_init_done(property);
      return;
    }

    py_init_by_self_ = true;

    // We met 'symbols not found' error when loading python modules while the
    // symbols are expected to be found in the python lib. We need to load the
    // python lib first.
    //
    // Refer to
    // https://mail.python.org/pipermail/new-bugs-announce/2008-November/003322.html?from_wecom=1
    load_python_lib();

    rte_py_initialize();

    // Before loading the rte python modules (extensions), we have to complete
    // sys.path first.
    complete_sys_path();

    rte_py_run_simple_string(
        "import sys\n"
        "print(sys.path)\n");

    const auto *sys_path = rte_py_get_path();
    RTE_LOGI("python initialized, sys.path: %s\n", sys_path);

    rte_py_mem_free((void *)sys_path);

    // Traverse the addon extensions directory and import module.
    rte_string_t *addon_extensions_path = get_addon_extensions_path();

    load_all_python_modules(addon_extensions_path);

    rte_string_destroy(addon_extensions_path);

    py_thread_state_ = rte_py_eval_save_thread();

    rte_env.on_init_done(property);
  }

  void on_create_instance(rte::rte_env_t &rte_env, const char *name,
                          void *context) override {
    // Create instance.
    RTE_ASSERT(0, "Should not happen.");
  }

  void on_create_instance_impl(rte::rte_env_t &rte_env, const char *name,
                               void *context) override {
    // Create instance.
    RTE_ASSERT(0, "Should not happen.");
  }

  void on_destroy_instance(rte::rte_env_t &rte_env, void *instance,
                           void *context) override {
    // Destroy instance.
    RTE_ASSERT(0, "Should not happen.");
  }

  void on_deinit(rte::rte_env_t &rte_env) override {
    // Do some de-initializations.
    if (py_thread_state_ != nullptr) {
      rte_py_eval_restore_thread(py_thread_state_);
    }

    if (py_init_by_self_) {
      int rc = rte_py_finalize();
      if (rc < 0) {
        RTE_LOGE("Failed to finalize python runtime, rc: %d", rc);
        RTE_ASSERT(0, "Should not happen.");
      }
    }

    rte_env.on_deinit_done();
  }

 private:
  void *py_thread_state_ = nullptr;
  bool py_init_by_self_ = false;
};

static rte::addon_t *g_py_init_default_extension_addon = nullptr;

AGORA_RTE_CONSTRUCTOR(____ctor_rte_declare_py_init_extension_addon____) {
  g_py_init_default_extension_addon = new py_init_addon_t();
  rte_addon_register_extension(
      "py_init_extension_cpp",
      g_py_init_default_extension_addon->get_c_addon());
}

AGORA_RTE_DESTRUCTOR(____dtor_rte_declare_py_init_extension_addon____) {
  if (g_py_init_default_extension_addon != nullptr) {
    rte_addon_unregister_extension(
        "py_init_extension_cpp",
        g_py_init_default_extension_addon->get_c_addon());
    delete g_py_init_default_extension_addon;
  }
}

}  // namespace default_extension
