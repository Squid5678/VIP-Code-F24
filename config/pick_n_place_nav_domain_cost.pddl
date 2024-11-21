(define (domain pick_and_place_nav)
    (:requirements :strips :typing :action-costs) 
    (:types object robot)

    (:predicates 
        (GRASPABLE ?x - object)
        (CONTAINABLE ?x - object)
        (carry ?r - robot ?x - object)
        (contain ?x - object ?y - object)
        (free ?r - robot)
        (close ?x - object ?y - object)
        (at-robot ?r ?y - object)
    )

    (:action navigate-to-pickable
        :parameters (?r - robot ?obj - object)
        :precondition 
        (and 
            (free ?r)
            (GRASPABLE ?obj)
            (not (carry ?r ?obj))
        )
        :effect 
        (and
            (at-robot ?r ?obj)
            (increase (total-cost) 1) ;; Assuming navigation cost is 1
        )
    )

    (:action navigate-to-container
        :parameters (?r - robot ?cont - object ?item - object)
        :precondition 
        (and 
            (carry ?r ?item)
            (CONTAINABLE ?cont)
        )
        :effect 
        (and
            (at-robot ?r ?cont)
            (increase (total-cost) 1) ;; Assuming navigation cost is 1
        )
    )

    (:action pickup
        :parameters (?x - object ?r - robot)
        :precondition 
        (and 
            (GRASPABLE ?x)
            (free ?r)
            (at-robot ?r ?x)
        )
        :effect 
        (and
            (carry ?r ?x)
            (not (free ?r))
            (increase (total-cost) 1) ;; Assuming pickup cost is 1
        )
    )

    (:action place 
        :parameters (?x - object ?r - robot ?z - object)
        :precondition 
        (and 
            (carry ?r ?x)
            (CONTAINABLE ?z)
            (at-robot ?r ?z)
        )
        :effect 
        (and
            (contain ?x ?z)
            (not (CONTAINABLE ?z))
            (free ?r)
            (increase (total-cost) 1) ;; Assuming place cost is 1
        )
    )
)
