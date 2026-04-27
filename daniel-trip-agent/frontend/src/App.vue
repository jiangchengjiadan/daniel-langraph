<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">
</script>

<style>
:root {
  color: #0f172a;
  background: #f8fafc;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

body {
  margin: 0;
  background: #f8fafc;
}

* {
  box-sizing: border-box;
}

#app {
  min-height: 100vh;
}
</style>
