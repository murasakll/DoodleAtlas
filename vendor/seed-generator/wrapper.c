/* Chiko adapter. Upstream code and SeedForge patches retain their MIT notices. */
#include "generator.h"
#include "util.h"
#include <stdlib.h>
#include <stdint.h>
#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif

API void *chiko_create(uint64_t seed) {
    Generator *g=malloc(sizeof(Generator));
    if(!g)return NULL;
    setupGenerator(g,MC_26_3,0);
    applySeed(g,DIM_OVERWORLD,seed);
    return g;
}
API void chiko_free(void *handle) { free(handle); }
API int chiko_biome(void *handle,int x,int y,int z) {
    return getBiomeAt((Generator*)handle,1,x,y,z);
}
API int chiko_grid(void *handle,int scale,int x,int y,int z,int side,int *out) {
    if(!handle||!out||side<1||side>256||(scale!=4&&scale!=16&&scale!=64&&scale!=256))return -1;
    Range r={0};r.scale=scale;r.x=x;r.z=z;r.sx=side;r.sz=side;r.y=y;r.sy=1;
    int *cache=allocCache((Generator*)handle,r);
    if(!cache)return -2;
    int result=genBiomes((Generator*)handle,cache,r);
    if(!result)for(int i=0;i<side*side;i++)out[i]=cache[i];
    free(cache);return result;
}
API const char *chiko_name(int biome) {
    if(biome==187)return "sulfur_caves";
    if(biome==188)return "dappled_forest";
    return biome2str(MC_26_3,biome);
}
