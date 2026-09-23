/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 bomwerk
 *
 * Compiled only in config-b. This is the translation unit that makes the linker
 * pull third_party/freertos/list.c into the binary, which is what turns "FreeRTOS
 * is present in the tree" into "FreeRTOS is in the product".
 *
 * Note it calls uxListInsertBounded() - a function that exists in NO FreeRTOS
 * release. The forked code is not merely vendored, it is reachable from main().
 * Nothing here runs a scheduler; no FreeRTOS task is ever created or started.
 */

#include "FreeRTOS.h"
#include "list.h"

/* The fork adds uxListInsertBounded() to list.c and declares it in NO header -
 * upstream list.h has no idea it exists. That is realistic vendor sloppiness, and
 * it is also why the prototype has to live here: calling an undeclared function is
 * an error under C99, not a warning. Keeping the declaration in our own file means
 * third_party/ still contains exactly one modified file. */
extern UBaseType_t uxListInsertBounded(List_t * const pxList,
                                       ListItem_t * const pxNewListItem,
                                       UBaseType_t uxMaxTraversal);

#define kBoundedInsertTraversalLimit ((UBaseType_t) 4U)
#define kSampleItemValue             ((TickType_t) 42U)

int nightmare_rtos_selftest(void)
{
    List_t sample_list;
    ListItem_t sample_item;
    UBaseType_t traversed;

    vListInitialise(&sample_list);
    vListInitialiseItem(&sample_item);
    sample_item.xItemValue = kSampleItemValue;

    /* THE FORK. Upstream FreeRTOS has vListInsert(); it has no bounded variant. */
    traversed = uxListInsertBounded(&sample_list, &sample_item,
                                    kBoundedInsertTraversalLimit);

    if (listCURRENT_LIST_LENGTH(&sample_list) != (UBaseType_t) 1U)
    {
        return 1;
    }
    if (traversed > kBoundedInsertTraversalLimit)
    {
        return 2;
    }
    if (uxListRemove(&sample_item) != (UBaseType_t) 0U)
    {
        return 3;
    }
    return 0;
}
