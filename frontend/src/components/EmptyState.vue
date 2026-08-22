<script setup lang="ts">
defineProps<{
  title: string
  body: string
}>()
</script>

<template>
  <div class="empty">
    <h2>{{ title }}</h2>
    <p>{{ body }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty {
  padding: 1.5rem 0;
}

h2 {
  margin: 0 0 0.35rem;
  font-size: 21px;
}

p {
  margin: 0;
  color: #495057;
}
</style>
